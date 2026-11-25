"""
Regression tests — attendance marks must persist (Nov 2026 recurrence).

Root cause covered: a best-effort helper (work-detail suggestion bump /
attendance→expense signal) swallowed a DB error inside save_attendance's
atomic block without its own savepoint. Postgres then silently rolled back
the AttendanceRecord on COMMIT while the view reported it as saved, so the
mark "disappeared" on the next page load.
"""
import datetime
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from employees.models import Employee

from .models import AttendanceRecord

ADMIN = 'TADM01'


class _Base(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='admin@example.test', username='admin', password='x', admin_id=ADMIN,
        )
        self.client.force_login(self.user)
        self.emp = Employee.objects.create(
            name='Test Worker', employee_id='T001', admin_id=ADMIN, base_salary=600,
        )

    def _save(self, records):
        r = self.client.post(
            reverse('attendance:save_attendance'),
            data=json.dumps(records), content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()

    def _load(self, day):
        r = self.client.get(
            reverse('attendance:load_attendance'),
            {'date_from': day, 'date_to': day},
        )
        return [x for x in r.json()['records'] if x['empPk'] == self.emp.pk]


class AttendancePersistsTests(_Base):
    def test_save_then_load_round_trip(self):
        day = (timezone.now() - datetime.timedelta(days=2)).date().isoformat()
        res = self._save([{'empId': 'T001', 'pk': self.emp.pk, 'date': day, 'status': 'Present'}])
        self.assertEqual(res['saved'], 1)
        self.assertEqual(res['savedRows'], [0])
        rows = self._load(day)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['date'], day)
        self.assertEqual(rows[0]['status'], 'Present')

    def test_long_work_details_still_persists_the_mark(self):
        # >200 chars used to raise DataError in the suggestion bump, which
        # silently rolled back the attendance row.
        day = (timezone.now() - datetime.timedelta(days=2)).date().isoformat()
        res = self._save([{
            'empId': 'T001', 'pk': self.emp.pk, 'date': day,
            'status': 'Present', 'workDetails': 'x' * 450,
        }])
        self.assertEqual(res['failures'], [])
        self.assertEqual(res['saved'], 1)
        self.assertTrue(AttendanceRecord.objects.filter(employee=self.emp, date=day).exists())
        self.assertEqual(len(self._load(day)), 1)

    def test_unresolvable_employee_is_reported_not_silently_skipped(self):
        day = (timezone.now() - datetime.timedelta(days=2)).date().isoformat()
        res = self._save([{'empId': 'NOPE', 'pk': 999999, 'date': day, 'status': 'Present'}])
        self.assertEqual(res['saved'], 0)
        self.assertEqual(res['savedRows'], [])
        self.assertEqual(len(res['failures']), 1)
        self.assertEqual(res['failures'][0]['rowIndex'], 0)


class AttendanceIstDateTests(_Base):
    def _at_utc(self, y, m, d, hh, mm):
        return datetime.datetime(y, m, d, hh, mm, tzinfo=datetime.timezone.utc)

    def test_afternoon_ist_save_lands_on_same_date(self):
        # 15:00 IST on 24 Nov 2026 == 09:30 UTC.
        now = self._at_utc(2026, 11, 24, 9, 30)
        with mock.patch('django.utils.timezone.now', return_value=now):
            res = self._save([{'empId': 'T001', 'pk': self.emp.pk,
                               'date': '2026-11-24', 'status': 'Present'}])
        self.assertEqual(res['saved'], 1)
        rec = AttendanceRecord.objects.get(employee=self.emp)
        self.assertEqual(rec.date, datetime.date(2026, 11, 24))
        self.assertEqual(len(self._load('2026-11-24')), 1)

    def test_early_morning_ist_today_is_not_rejected_as_future(self):
        # 01:30 IST on 25 Nov 2026 == 20:00 UTC on 24 Nov.
        now = self._at_utc(2026, 11, 24, 20, 0)
        with mock.patch('django.utils.timezone.now', return_value=now):
            res = self._save([{'empId': 'T001', 'pk': self.emp.pk,
                               'date': '2026-11-25', 'status': 'Present'}])
        self.assertEqual(res['failures'], [])
        self.assertEqual(res['saved'], 1)
