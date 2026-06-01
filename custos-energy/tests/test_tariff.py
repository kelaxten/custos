"""
Tests for the Custos Energy tariff engine.

Run:  python -m pytest tests/ -v
  or: python -m unittest discover -s tests
"""

import unittest
from datetime import date, datetime

from custos_energy.tariff import (
    OFF_PEAK, MID_PEAK, PEAK,
    get_tariff, next_change, is_holiday, holiday_name,
    holidays_for_year, _nth_weekday, _last_weekday,
)


def dt(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi)


class TestWeekdaySchedule(unittest.TestCase):
    # 2026-06-01 is a Monday.
    def test_off_peak_window(self):
        for h in range(0, 6):
            self.assertEqual(get_tariff(dt(2026, 6, 1, h)), OFF_PEAK, h)

    def test_morning_midpeak(self):
        for h in range(6, 17):
            self.assertEqual(get_tariff(dt(2026, 6, 1, h)), MID_PEAK, h)

    def test_evening_peak(self):
        for h in range(17, 21):
            self.assertEqual(get_tariff(dt(2026, 6, 1, h)), PEAK, h)

    def test_late_midpeak(self):
        for h in range(21, 24):
            self.assertEqual(get_tariff(dt(2026, 6, 1, h)), MID_PEAK, h)

    def test_boundaries_exact(self):
        self.assertEqual(get_tariff(dt(2026, 6, 1, 5, 59)), OFF_PEAK)
        self.assertEqual(get_tariff(dt(2026, 6, 1, 6, 0)), MID_PEAK)
        self.assertEqual(get_tariff(dt(2026, 6, 1, 16, 59)), MID_PEAK)
        self.assertEqual(get_tariff(dt(2026, 6, 1, 17, 0)), PEAK)
        self.assertEqual(get_tariff(dt(2026, 6, 1, 20, 59)), PEAK)
        self.assertEqual(get_tariff(dt(2026, 6, 1, 21, 0)), MID_PEAK)

    def test_saturday_has_peak(self):
        # 2026-06-06 is a Saturday — Mon-Sat schedule, so peak applies.
        self.assertEqual(get_tariff(dt(2026, 6, 6, 18)), PEAK)


class TestSundaySchedule(unittest.TestCase):
    # 2026-06-07 is a Sunday.
    def test_sunday_no_peak(self):
        self.assertEqual(get_tariff(dt(2026, 6, 7, 18)), MID_PEAK)

    def test_sunday_off_peak_still_applies(self):
        self.assertEqual(get_tariff(dt(2026, 6, 7, 3)), OFF_PEAK)

    def test_sunday_daytime_midpeak(self):
        self.assertEqual(get_tariff(dt(2026, 6, 7, 12)), MID_PEAK)


class TestHolidays(unittest.TestCase):
    def test_six_holidays_present(self):
        hs = holidays_for_year(2026)
        names = set(hs.values())
        self.assertEqual(names, {
            "New Year's Day", "Memorial Day", "Independence Day",
            "Labor Day", "Thanksgiving Day", "Christmas Day",
        })
        self.assertEqual(len(hs), 6)

    def test_fixed_dates(self):
        hs = holidays_for_year(2026)
        self.assertEqual(hs[date(2026, 1, 1)], "New Year's Day")
        self.assertEqual(hs[date(2026, 7, 4)], "Independence Day")
        self.assertEqual(hs[date(2026, 12, 25)], "Christmas Day")

    def test_memorial_day_is_last_monday_may(self):
        md = _last_weekday(2026, 5, 0)
        self.assertEqual(md.month, 5)
        self.assertEqual(md.weekday(), 0)            # Monday
        self.assertGreaterEqual(md.day, 25)          # last Monday is >= 25th
        self.assertTrue(is_holiday(md))

    def test_labor_day_is_first_monday_sep(self):
        ld = _nth_weekday(2026, 9, 0, 1)
        self.assertEqual(ld.month, 9)
        self.assertEqual(ld.weekday(), 0)
        self.assertLessEqual(ld.day, 7)
        self.assertTrue(is_holiday(ld))

    def test_thanksgiving_is_fourth_thursday_nov(self):
        tg = _nth_weekday(2026, 11, 3, 4)
        self.assertEqual(tg.month, 11)
        self.assertEqual(tg.weekday(), 3)            # Thursday
        self.assertTrue(22 <= tg.day <= 28)
        self.assertTrue(is_holiday(tg))

    def test_holiday_uses_sunday_schedule(self):
        # Christmas 2026 is a Friday; on a normal Friday 6pm would be PEAK,
        # but as a holiday it must be MID_PEAK (no peak).
        xmas = datetime(2026, 12, 25, 18)
        self.assertEqual(xmas.weekday(), 4)          # Friday
        self.assertEqual(get_tariff(xmas), MID_PEAK)
        self.assertEqual(holiday_name(xmas.date()), "Christmas Day")

    def test_non_holiday_weekday_unaffected(self):
        # 2026-12-24 (Thu) is not a holiday; 6pm should be PEAK.
        self.assertEqual(get_tariff(dt(2026, 12, 24, 18)), PEAK)

    def test_observed_flag_adds_weekend_observance(self):
        # 2027-12-25 is a Saturday -> observed Friday 12-24 when OBSERVED=True.
        self.assertEqual(date(2027, 12, 25).weekday(), 5)
        self.assertFalse(is_holiday(date(2027, 12, 24), observed=False))
        self.assertTrue(is_holiday(date(2027, 12, 24), observed=True))


class TestNextChange(unittest.TestCase):
    def test_offpeak_to_midpeak(self):
        when, nxt = next_change(dt(2026, 6, 1, 3))   # Mon 3am off-peak
        self.assertEqual(nxt, MID_PEAK)
        self.assertEqual(when, dt(2026, 6, 1, 6))

    def test_midpeak_to_peak(self):
        when, nxt = next_change(dt(2026, 6, 1, 12))  # Mon noon mid-peak
        self.assertEqual(nxt, PEAK)
        self.assertEqual(when, dt(2026, 6, 1, 17))

    def test_peak_to_midpeak(self):
        when, nxt = next_change(dt(2026, 6, 1, 18))  # Mon 6pm peak
        self.assertEqual(nxt, MID_PEAK)
        self.assertEqual(when, dt(2026, 6, 1, 21))

    def test_saturday_evening_into_sunday(self):
        # Sat 2026-06-06 10pm is mid-peak; next change is Sun midnight off-peak.
        when, nxt = next_change(dt(2026, 6, 6, 22))
        self.assertEqual(nxt, OFF_PEAK)
        self.assertEqual(when, dt(2026, 6, 7, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
