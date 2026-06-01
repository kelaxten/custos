"""
Custos Energy — Time-of-Use tariff engine.

Pure-stdlib, dependency-free. This is the auditable core of the energy
optimization module: given a datetime, it returns which TOU period is in
effect and the $/kWh rate. Everything else (MQTT publishing, Home Assistant
automations) is plumbing around the functions defined here.

Rate schedule (configurable via custos_energy.config):

  Monday-Saturday
    Off-Peak  12am-6am          $0.0882 /kWh
    Mid-Peak  6am-5pm, 9pm-12am  $0.1543 /kWh
    Peak      5pm-9pm            $0.1763 /kWh

  Sundays & Holidays
    Off-Peak  12am-6am          $0.0882 /kWh
    Mid-Peak  6am-12am          $0.1543 /kWh
    (no peak period)

  Base service charge            $0.4262 /day

  Holidays: New Year's Day, Memorial Day, Independence Day,
            Labor Day, Thanksgiving Day, Christmas Day.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

# --- Period identifiers --------------------------------------------------

OFF_PEAK = "off_peak"
MID_PEAK = "mid_peak"
PEAK = "peak"

# --- Default rates ($/kWh) and base charge ($/day) -----------------------
# Override at runtime via custos_energy.config (env vars) so the same code
# works if your utility changes rates.

DEFAULT_RATES = {
    OFF_PEAK: 0.0882,
    MID_PEAK: 0.1543,
    PEAK: 0.1763,
}
DEFAULT_BASE_CHARGE_PER_DAY = 0.4262

# Period boundaries, expressed as hour-of-day cut points.
OFF_PEAK_END_HOUR = 6      # 06:00 — off-peak runs [00:00, 06:00)
PEAK_START_HOUR = 17       # 17:00 — peak runs [17:00, 21:00) on Mon-Sat
PEAK_END_HOUR = 21         # 21:00


# --- Holiday computation -------------------------------------------------

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the date of the n-th `weekday` (Mon=0..Sun=6) in month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the date of the last `weekday` (Mon=0..Sun=6) in month."""
    last_dom = calendar.monthrange(year, month)[1]
    last = date(year, month, last_dom)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def holidays_for_year(year: int, observed: bool = False) -> dict[date, str]:
    """
    Map of {date: holiday name} for the six tariff holidays in `year`.

    If `observed` is True, fixed-date holidays that land on a weekend are
    *also* added on their federally-observed weekday (Sat -> prior Fri,
    Sun -> following Mon). Whether your utility honors observed dates or the
    literal calendar date is a billing-policy question — confirm it and set
    OBSERVED accordingly. Default is literal-date matching.
    """
    fixed = {
        date(year, 1, 1): "New Year's Day",
        date(year, 7, 4): "Independence Day",
        date(year, 12, 25): "Christmas Day",
    }
    floating = {
        _last_weekday(year, 5, 0): "Memorial Day",        # last Monday in May
        _nth_weekday(year, 9, 0, 1): "Labor Day",          # first Monday in Sep
        _nth_weekday(year, 11, 3, 4): "Thanksgiving Day",  # 4th Thursday in Nov
    }
    result: dict[date, str] = {}
    result.update(fixed)
    result.update(floating)

    if observed:
        for d, name in list(fixed.items()):
            if d.weekday() == 5:        # Saturday -> observed Friday
                result.setdefault(d - timedelta(days=1), name + " (observed)")
            elif d.weekday() == 6:      # Sunday -> observed Monday
                result.setdefault(d + timedelta(days=1), name + " (observed)")
    return result


def is_holiday(d: date, observed: bool = False) -> bool:
    return d in holidays_for_year(d.year, observed=observed)


def holiday_name(d: date, observed: bool = False) -> str | None:
    return holidays_for_year(d.year, observed=observed).get(d)


# --- Tariff resolution ---------------------------------------------------

def uses_sunday_schedule(dt: datetime, observed: bool = False) -> bool:
    """True if `dt` falls on a Sunday or a holiday (no peak period)."""
    return dt.weekday() == 6 or is_holiday(dt.date(), observed=observed)


def get_tariff(dt: datetime, observed: bool = False) -> str:
    """
    Return the TOU period (OFF_PEAK / MID_PEAK / PEAK) in effect at `dt`.

    weekday(): Monday=0 .. Saturday=5 .. Sunday=6. Saturday uses the
    Mon-Sat schedule (it *does* have a peak window); only Sunday and the
    listed holidays drop the peak window.
    """
    hour = dt.hour

    if hour < OFF_PEAK_END_HOUR:               # [00:00, 06:00)
        return OFF_PEAK

    if uses_sunday_schedule(dt, observed=observed):
        return MID_PEAK                         # Sun/holiday: 6am-12am all mid

    # Monday-Saturday
    if PEAK_START_HOUR <= hour < PEAK_END_HOUR:  # [17:00, 21:00)
        return PEAK
    return MID_PEAK                              # 6am-5pm and 9pm-12am


def rate_for(dt: datetime, rates: dict | None = None,
             observed: bool = False) -> float:
    rates = rates or DEFAULT_RATES
    return rates[get_tariff(dt, observed=observed)]


def next_change(dt: datetime, observed: bool = False):
    """
    Return (datetime_of_next_period_change, next_period).

    Used by the pre-conditioning automations (e.g. pre-cool before the 5pm
    peak). Evaluates the fixed daily boundaries over the next 48h and returns
    the first one whose period differs from the current period — this also
    correctly captures Sat->Sun and holiday transitions.
    """
    current = get_tariff(dt, observed=observed)
    candidates = []
    for day_offset in (0, 1, 2):
        d = dt.date() + timedelta(days=day_offset)
        for hh in (0, OFF_PEAK_END_HOUR, PEAK_START_HOUR, PEAK_END_HOUR):
            candidates.append(datetime.combine(d, time(hh, 0)))
    for c in sorted(c for c in candidates if c > dt):
        if get_tariff(c, observed=observed) != current:
            return c, get_tariff(c, observed=observed)
    return None, current


# --- Cost helpers --------------------------------------------------------

def monthly_base_charge(days_in_period: int,
                        base_per_day: float = DEFAULT_BASE_CHARGE_PER_DAY) -> float:
    """Fixed service charge accrued over a billing period."""
    return round(days_in_period * base_per_day, 4)


def snapshot(dt: datetime, rates: dict | None = None,
             observed: bool = False) -> dict:
    """A single dict describing the tariff state at `dt` — the MQTT payload."""
    rates = rates or DEFAULT_RATES
    period = get_tariff(dt, observed=observed)
    change_at, next_period = next_change(dt, observed=observed)
    return {
        "period": period,
        "rate": rates[period],
        "schedule": "sunday_holiday" if uses_sunday_schedule(dt, observed) else "weekday",
        "is_holiday": is_holiday(dt.date(), observed=observed),
        "holiday_name": holiday_name(dt.date(), observed=observed),
        "next_change": change_at.isoformat() if change_at else None,
        "next_period": next_period,
        "next_rate": rates[next_period],
        "as_of": dt.isoformat(timespec="seconds"),
    }
