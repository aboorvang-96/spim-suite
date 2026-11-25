"""Regression tests for employees.paid_days — cycle 26 Oct → 25 Nov 2026."""

from decimal import Decimal

from django.test import SimpleTestCase

from .paid_days import day_weight, summarize_paid_days

CYCLE_DAYS = 31  # 26 Oct → 25 Nov


class DailyBasisPaidDaysTests(SimpleTestCase):
    def test_aakash_daily_present_plus_week_off_only(self):
        r = summarize_paid_days(
            {'present': 17, 'week_off': 1, 'holiday': 3, 'leave': 6},
            is_daily=True, rate=600, cycle_days=CYCLE_DAYS,
        )
        self.assertEqual(r['paid_days'], Decimal('18'))
        self.assertEqual(r['attendance_earnings'], Decimal('10800.00'))

    def test_ajay_daily_present_plus_week_off_only(self):
        r = summarize_paid_days(
            {'present': 11, 'week_off': 1, 'holiday': 3, 'leave': 13},
            is_daily=True, rate=1000, cycle_days=CYCLE_DAYS,
        )
        self.assertEqual(r['paid_days'], Decimal('12'))
        self.assertEqual(r['attendance_earnings'], Decimal('12000.00'))

    def test_daily_half_day_not_counted(self):
        r = summarize_paid_days(
            {'present': 10, 'half_day': 4},
            is_daily=True, rate=500, cycle_days=CYCLE_DAYS,
        )
        self.assertEqual(r['paid_days'], Decimal('10'))
        self.assertEqual(r['attendance_earnings'], Decimal('5000.00'))
        self.assertEqual(day_weight('half_day', True), Decimal('0'))
        self.assertEqual(day_weight('holiday', True), Decimal('0'))

    def test_daily_week_off_counted_with_zero_present(self):
        r = summarize_paid_days(
            {'week_off': 2, 'leave': 5},
            is_daily=True, rate=700, cycle_days=CYCLE_DAYS,
        )
        self.assertEqual(r['paid_days'], Decimal('2'))
        self.assertEqual(r['attendance_earnings'], Decimal('1400.00'))

    def test_daily_no_records_pays_zero(self):
        r = summarize_paid_days({}, is_daily=True, rate=600,
                                cycle_days=CYCLE_DAYS, has_records=False)
        self.assertEqual(r['attendance_earnings'], Decimal('0.00'))


class MonthlyPaidDaysTests(SimpleTestCase):
    def test_monthly_counts_holiday_and_half_day(self):
        # 20 P + 1 WO + 3 H + 2 HD (=1) + 5 L → 25 paid days of 31.
        r = summarize_paid_days(
            {'present': 20, 'week_off': 1, 'holiday': 3, 'half_day': 2, 'leave': 5},
            is_daily=False, rate=31000, cycle_days=CYCLE_DAYS,
        )
        self.assertEqual(r['paid_days'], Decimal('25'))
        self.assertEqual(r['per_day_rate'], Decimal('1000'))
        self.assertEqual(r['attendance_earnings'], Decimal('25000.00'))

    def test_monthly_no_week_off_and_leave_unpaid(self):
        r = summarize_paid_days(
            {'present': 1, 'no_week_off': 4, 'leave': 4},
            is_daily=False, rate=31000, cycle_days=CYCLE_DAYS,
        )
        self.assertEqual(r['paid_days'], Decimal('1'))

    def test_monthly_no_records_falls_back_to_full_salary(self):
        r = summarize_paid_days({}, is_daily=False, rate=31000,
                                cycle_days=CYCLE_DAYS, has_records=False)
        self.assertEqual(r['paid_days'], Decimal('31'))
        self.assertEqual(r['attendance_earnings'], Decimal('31000.00'))
