"""
Site linkage across Income / Expense / Attendance / Salary / Projects.

Covers the shared helper finance.services.site_cards:
  (i)   a site created via Income appears in Expense and in the
        Attendance / Salary / Projects selectors;
  (ii)  a site created via Expense appears in Income;
  (iii) "(No Site)" appears exactly once on Income and Expense with equal
        figures (null, '' and the literal "(No Site)" share one bucket);
  (iv)  Income "Total Debits" == Σ Income site-card debits (incl. No Site).
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.date_utils import today_ist
from finance.models import Transaction
from finance.services.site_cards import (
    NO_SITE_LABEL, NO_SITE_VALUE, ensure_site, site_choice_names, site_key,
)
from income.models import Income

ADMIN = 'TSITE1'


class _Base(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='site-admin@example.test', username='siteadmin', password='x',
            admin_id=ADMIN, role='admin',
        )
        self.client.force_login(self.user)
        self.today = today_ist()

    def _expense(self, site, amount):
        return Transaction.objects.create(
            user=self.user, type='expense', amount=Decimal(amount),
            date=self.today, location_site=site, admin_id=ADMIN,
        )

    def _income(self, site, amount):
        return Income.objects.create(
            user=self.user, admin_id=ADMIN, amount=Decimal(amount),
            date=self.today, location_site=site,
        )

    def _cards(self, url_name):
        r = self.client.get(reverse(url_name))
        self.assertEqual(r.status_code, 200)
        return r, {g['site_key']: g for g in r.context['sites_grouped']}


class NoSiteKeyTests(TestCase):
    def test_all_no_site_shapes_share_one_key(self):
        for raw in (None, '', '   ', '(No Site)', '(no site)', NO_SITE_VALUE):
            self.assertEqual(site_key(raw), '')
        self.assertEqual(site_key(' Andhra '), 'andhra')

    def test_ensure_site_no_site_creates_nothing(self):
        from projects.models import Site
        self.assertEqual(ensure_site(ADMIN, '(No Site)'), '')
        self.assertEqual(ensure_site(ADMIN, NO_SITE_VALUE), '')
        self.assertFalse(Site.objects.filter(admin_id=ADMIN).exists())


class SharedCreatePathTests(_Base):
    def test_site_created_via_income_appears_everywhere(self):
        from income.views import _normalize_site_or_office  # Income write path
        stored = _normalize_site_or_office(ADMIN, 'Fresh Income Site', self.user)
        self.assertEqual(stored, 'Fresh Income Site')

        # Expense site list + cards universe
        from finance.views import _location_sites_json as exp_sites
        self.assertIn('Fresh Income Site', json.loads(exp_sites(self.user)))
        # Attendance bulk-entry dropdown source
        from attendance.views import _shared_site_names as att_sites
        self.assertIn('Fresh Income Site', att_sites(ADMIN))
        # Salary site filter
        from employees.views import _salary_site_options
        sal = _salary_site_options(ADMIN)
        self.assertIn('Fresh Income Site', sal)
        self.assertEqual(sal[-1], NO_SITE_LABEL)
        # Projects site filter
        from projects.views import _shared_site_names as proj_sites
        names = proj_sites(ADMIN)
        self.assertIn('Fresh Income Site', names)
        self.assertIn(NO_SITE_LABEL, names)

    def test_site_created_via_expense_appears_in_income(self):
        r = self.client.post(
            reverse('expenses:add'),
            {'date': self.today.isoformat(), 'amount': '150.00',
             'location_site': 'Fresh Expense Site', 'payment_mode': 'cash',
             'type': 'expense'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200, r.content)
        from income.views import _location_sites_json as inc_sites
        self.assertIn('Fresh Expense Site', json.loads(inc_sites(self.user)))
        _, cards = self._cards('income:list')
        self.assertIn('fresh expense site', cards)
        self.assertEqual(cards['fresh expense site']['debit'], Decimal('150.00'))

    def test_case_insensitive_no_duplicate_site(self):
        from projects.models import Site
        ensure_site(ADMIN, 'KKNPP', self.user)
        self.assertEqual(ensure_site(ADMIN, 'kknpp', self.user), 'KKNPP')
        self.assertEqual(Site.objects.filter(admin_id=ADMIN, name__iexact='kknpp').count(), 1)

    def test_selectors_offer_no_site_once(self):
        names = site_choice_names(ADMIN, extra=['', '(No Site)', 'A'])
        self.assertEqual(names.count(NO_SITE_LABEL), 1)


class NoSiteBucketTests(_Base):
    def setUp(self):
        super().setUp()
        ensure_site(ADMIN, 'Andhra', self.user)
        self._expense(None, '100.00')
        self._expense('', '20.00')
        self._expense('(No Site)', '10.00')
        self._expense('Andhra', '40.00')
        self._income('', '500.00')
        self._income('Andhra', '70.00')

    def test_no_site_once_and_equal_on_both_pages(self):
        r_inc, inc = self._cards('income:list')
        r_exp, exp = self._cards('expenses:list')
        for page in (r_inc, r_exp):
            keys = [g['site_key'] for g in page.context['sites_grouped']]
            self.assertEqual(keys.count(''), 1)
            labels = [g['site'] for g in page.context['sites_grouped']]
            self.assertEqual(labels.count(NO_SITE_LABEL), 1)
        for k in ('', 'andhra'):
            self.assertEqual(inc[k]['credit'], exp[k]['credit'])
            self.assertEqual(inc[k]['debit'], exp[k]['debit'])
            self.assertEqual(inc[k]['balance'], exp[k]['balance'])
        self.assertEqual(inc['']['debit'], Decimal('130.00'))
        self.assertEqual(inc['']['credit'], Decimal('500.00'))
        self.assertEqual(inc['andhra']['debit'], Decimal('40.00'))
        self.assertEqual(set(inc), set(exp))

    def test_income_total_debits_equals_sum_of_cards(self):
        r, cards = self._cards('income:list')
        total = sum((g['debit'] for g in cards.values()), Decimal('0'))
        self.assertEqual(total, Decimal(r.context['cycle_debits']))
        credits = sum((g['credit'] for g in cards.values()), Decimal('0'))
        self.assertEqual(credits, Decimal(r.context['cycle_credits']))

    def test_expense_total_equals_sum_of_cards(self):
        r, cards = self._cards('expenses:list')
        total = sum((g['debit'] for g in cards.values()), Decimal('0'))
        self.assertEqual(float(total), float(r.context['total_expense']))
