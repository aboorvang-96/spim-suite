from decimal import Decimal

from django.test import SimpleTestCase

from .utils import compute_net_pay, compute_net_pay_for_record


class _Rec:
    def __init__(self, **kw):
        self.ot_allowance = kw.get('ot_allowance', 0)
        self.advance_pay = kw.get('advance_pay', 0)
        self.total_deduction = kw.get('total_deduction', 0)
        self.food_allowance = kw.get('food_allowance', 0)
        self.food_usage = kw.get('food_usage', 0)


class NetPayFormulaTests(SimpleTestCase):
    def test_net_pay_includes_food_adjustment(self):
        # CHANDRU: food allowance with no usage is added.
        self.assertEqual(
            compute_net_pay('37045.16', food_allowance=657, food_usage=0),
            Decimal('37702.16'),
        )
        # DASARATHAN: deduction and food overshoot both reduce net.
        self.assertEqual(
            compute_net_pay('17193.55', deduction=1557, food_allowance=0, food_usage=907),
            Decimal('14729.55'),
        )

    def test_zero(self):
        self.assertEqual(compute_net_pay(0, 0, 0, 0, 0, 0), Decimal('0'))

    def test_negative_food_adjustment_reduces_net(self):
        self.assertEqual(
            compute_net_pay(1000, food_allowance=100, food_usage=350),
            Decimal('750'),
        )

    def test_none_values_treated_as_zero(self):
        self.assertEqual(compute_net_pay(None, None, None, None, None, None), Decimal('0'))
        self.assertEqual(compute_net_pay('500', ot=None, food_usage=None), Decimal('500'))

    def test_full_formula(self):
        self.assertEqual(
            compute_net_pay(1000, ot=200, advance=50, deduction=30,
                            food_allowance=100, food_usage=40),
            Decimal('1180'),
        )

    def test_record_helper_matches_and_handles_missing_record(self):
        rec = _Rec(food_allowance=657)
        self.assertEqual(compute_net_pay_for_record(Decimal('37045.16'), rec), Decimal('37702.16'))
        self.assertEqual(compute_net_pay_for_record(Decimal('100'), None), Decimal('100'))
