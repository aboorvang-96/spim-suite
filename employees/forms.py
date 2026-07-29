from django import forms
from .models import Employee, BankDetail, PFDetail, SalaryUpdate


class EmployeeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in [
            'employee_id', 'mobile_app_password', 'department', 'fixed_allowance',
            'joining_date', 'status', 'job_role', 'level', 'mobile', 'branch',
        ]:
            if field in self.fields:
                self.fields[field].required = False

    def clean_employee_id(self):
        return (self.cleaned_data.get('employee_id') or '').strip()

    class Meta:
        model = Employee
        # NOTE: base_salary intentionally removed from the form (Task 3 / 2026-05-24).
        # The Employee.base_salary column still exists in the model — it is now
        # populated automatically from SalaryStructure(role + level) at create
        # time via employees.views._apply_role_level_salary. Existing rows keep
        # whatever value they had; absence of the field in the form means an
        # edit submission no longer overwrites it.
        fields = [
            'name', 'employee_id', 'designation', 'department',
            'location', 'site', 'fixed_allowance',
            'joining_date', 'status', 'mobile_app_password',
            'job_role', 'level', 'mobile', 'branch',
            # Admin-only flag: marks this row as a Vehicle so the Employee
            # Master / Salary / Attendance modules list it under "Vehicles".
            # Purely a categorization toggle; no business logic depends on it.
            'is_vehicle',
        ]
        widgets = {
            'name':                forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Ravi Kumar'}),
            'employee_id':         forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. SPIM001'}),
            'designation':         forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Site Engineer'}),
            'department':          forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Operations'}),
            'location':            forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Tirunelveli'}),
            'site':                forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Site 1 / Valliyur'}),
            'fixed_allowance':     forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 5000'}),
            'joining_date':        forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'status':              forms.Select(attrs={'class': 'form-input'}),
            'mobile_app_password': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. SPIM@4821'}),
            'job_role':            forms.Select(attrs={'class': 'form-input'}),
            'level':               forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. L1'}),
            'mobile':              forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. +91 9876543210'}),
            'branch':              forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Tirunelveli HQ'}),
            'is_vehicle':          forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class BankDetailForm(forms.ModelForm):
    class Meta:
        model = BankDetail
        fields = ['bank_name', 'account_holder', 'account_number', 'ifsc_code', 'branch', 'status']
        widgets = {
            'bank_name':      forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Canara Bank'}),
            'account_holder': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Account holder'}),
            'account_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Account number'}),
            'ifsc_code':      forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. CNRB0001234'}),
            'branch':         forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Branch'}),
            'status':         forms.Select(attrs={'class': 'form-input'}),
        }


class PFDetailForm(forms.ModelForm):
    class Meta:
        model = PFDetail
        fields = ['pf_number', 'uan_number', 'esic_number', 'employee_contribution', 'employer_contribution', 'joining_date', 'status']
        widgets = {
            'pf_number':             forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'PF Number'}),
            'uan_number':            forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'UAN Number'}),
            'esic_number':           forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ESIC Number'}),
            'employee_contribution': forms.NumberInput(attrs={'class': 'form-input'}),
            'employer_contribution': forms.NumberInput(attrs={'class': 'form-input'}),
            'joining_date':          forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'status':                forms.Select(attrs={'class': 'form-input'}),
        }


class SalaryForm(forms.ModelForm):
    class Meta:
        model = SalaryUpdate
        fields = ['month', 'basic_salary', 'extra_allowance', 'ot_allowance', 'advance_pay', 'total_deduction', 'net_pay', 'food_allowance', 'food_usage']
        widgets = {
            'month':           forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'basic_salary':    forms.NumberInput(attrs={'class': 'form-input'}),
            'extra_allowance': forms.NumberInput(attrs={'class': 'form-input'}),
            'ot_allowance':    forms.NumberInput(attrs={'class': 'form-input'}),
            'advance_pay':     forms.NumberInput(attrs={'class': 'form-input'}),
            'total_deduction': forms.NumberInput(attrs={'class': 'form-input'}),
            'net_pay':         forms.NumberInput(attrs={'class': 'form-input'}),
            'food_allowance':  forms.NumberInput(attrs={'class': 'form-input'}),
            'food_usage':      forms.NumberInput(attrs={'class': 'form-input'}),
        }
