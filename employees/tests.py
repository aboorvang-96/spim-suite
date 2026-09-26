from django.test import TestCase

from .forms import EmployeeForm
from .models import Employee
from .utils import normalize_employee_id


class NormalizeEmployeeIdTests(TestCase):
    def test_normalize_variants(self):
        self.assertEqual(normalize_employee_id('SPIM020'), 'SPIM020')
        self.assertEqual(normalize_employee_id('  spim020\n'), 'SPIM020')
        self.assertEqual(normalize_employee_id('SPIM 020'), 'SPIM020')
        self.assertEqual(normalize_employee_id('SPIM-020'), 'SPIM020')
        self.assertEqual(normalize_employee_id('spim.020'), 'SPIM020')
        self.assertEqual(normalize_employee_id(None), '')


class EmployeeFormDuplicateTests(TestCase):
    ADMIN = 'ADMTEST01'

    def setUp(self):
        self.existing = Employee.objects.create(
            admin_id=self.ADMIN,
            name='PRAVIN R',
            employee_id='SPIM020',
        )

    def _post(self, emp_id, **extra):
        data = {
            'name': 'New Person',
            'employee_id': emp_id,
            'designation': 'Site Engineer',
            'location': 'Tirunelveli',
            'site': 'Site 1',
        }
        data.update(extra)
        return data

    def test_exact_duplicate_rejected_with_friendly_message(self):
        form = EmployeeForm(self._post('SPIM020'), admin_id=self.ADMIN)
        self.assertFalse(form.is_valid())
        err = ' '.join(form.errors['employee_id'])
        self.assertIn('SPIM020', err)
        self.assertIn('PRAVIN R', err)

    def test_case_and_whitespace_variants_rejected(self):
        for variant in ['spim020', '  SPIM 020  ', 'SPIM-020', 'spim020\n']:
            form = EmployeeForm(self._post(variant), admin_id=self.ADMIN)
            self.assertFalse(form.is_valid(), f"expected {variant!r} to collide")
            err = ' '.join(form.errors['employee_id'])
            self.assertIn('PRAVIN R', err)
            # When input differs from normalized form, message must show both.
            if variant.strip() != 'SPIM020':
                self.assertIn('normalize', err.lower())

    def test_fresh_id_accepted_and_stored_normalized(self):
        form = EmployeeForm(self._post(' spim999 '), admin_id=self.ADMIN)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['employee_id'], 'SPIM999')

    def test_edit_self_does_not_falsely_collide(self):
        form = EmployeeForm(
            {
                'name': self.existing.name,
                'employee_id': 'SPIM020',
                'designation': 'Site Engineer',
                'location': 'Tirunelveli',
                'site': 'Site 1',
            },
            instance=self.existing,
            admin_id=self.ADMIN,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['employee_id'], 'SPIM020')
