"""
Expense Manager site panel: one row per (site, date).

Regression for "each category saves into a separate row": adding Food then
Travel for the same site + date must show ONE row with both columns, and
saving a column must never touch the other columns of that day.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.date_utils import today_ist
from finance.models import Transaction

ADMIN = 'TDAYROW1'
SITE = 'KUMILAMPADU'
CATS = ('food', 'room', 'diesel', 'travel', 'ticket', 'other')


class ExpenseDayRowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='dayrow-admin@example.test', username='dayrowadmin', password='x',
            admin_id=ADMIN, role='admin',
        )
        self.client.force_login(self.user)
        self.today = today_ist()
        self.url = reverse('expenses:save_day')

    def _post(self, mode='new', orig=None, remarks='', orig_remarks='', **vals):
        orig = orig or {}
        data = {'mode': mode, 'site': SITE, 'date': self.today.isoformat(),
                'remarks': remarks, 'orig_remarks': orig_remarks}
        for c in CATS:
            data[f'cat_{c}'] = vals.get(c, orig.get(c, ''))
            data[f'orig_{c}'] = orig.get(c, '')
        return self.client.post(self.url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def _day_rows(self):
        r = self.client.get(reverse('expenses:list'))
        self.assertEqual(r.status_code, 200)
        for g in r.context['sites_grouped']:
            if g['site_key'] == SITE.lower():
                return [row for row in g['card_rows'] if row['kind'] == 'expense']
        return []

    def test_food_then_travel_same_date_is_one_row(self):
        self.assertEqual(self._post(food='200').status_code, 200)
        r = self._post(travel='500')   # second +Add Row, same site + date
        self.assertEqual(r.status_code, 200)
        day = r.json()['day']
        self.assertEqual(day['cats']['food']['amount'], '200.00')
        self.assertEqual(day['cats']['travel']['amount'], '500.00')
        rows = self._day_rows()
        self.assertEqual(len(rows), 1)
        cats = {c['key']: c for c in rows[0]['day']['cat_list']}
        self.assertEqual(cats['food']['amount'], Decimal('200'))
        self.assertEqual(cats['travel']['amount'], Decimal('500'))

    def test_edit_one_column_keeps_others(self):
        self._post(food='200', travel='500', remarks='site visit')
        r = self._post(mode='edit', orig={'food': '200.00', 'travel': '500.00'},
                       food='250', orig_remarks='site visit', remarks='site visit')
        self.assertEqual(r.status_code, 200)
        amounts = dict(Transaction.objects.filter(admin_id=ADMIN)
                       .values_list('expense_category', 'amount'))
        self.assertEqual(amounts, {'food': Decimal('250.00'), 'travel': Decimal('500.00')})

    def test_new_row_does_not_overwrite_filled_column(self):
        self._post(food='200')
        r = self._post(food='300')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Transaction.objects.get(admin_id=ADMIN).amount, Decimal('200.00'))

    def test_column_with_multiple_records_is_not_merged(self):
        for amt in ('100', '150'):
            Transaction.objects.create(
                user=self.user, type='expense', expense_category='food',
                amount=Decimal(amt), date=self.today, location_site=SITE, admin_id=ADMIN)
        r = self._post(mode='edit', orig={'food': '250.00'}, food='300')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Transaction.objects.filter(admin_id=ADMIN).count(), 2)

    def test_clearing_a_column_deletes_only_that_record(self):
        self._post(food='200', diesel='900')
        r = self._post(mode='edit', orig={'food': '200.00', 'diesel': '900.00'}, food='')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(Transaction.objects.filter(admin_id=ADMIN)
                              .values_list('expense_category', flat=True)), ['diesel'])
