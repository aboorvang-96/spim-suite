from django import forms
from .models import Employee, BankDetail, PFDetail, Salary

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['name', 'role', 'location', 'site', 'base_salary']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Ravi Kumar'}),
            'role': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Site Engineer'}),
            'location': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Tirunelveli'}),
            'site': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Site 1 / Valliyur'}),
            'base_salary': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 45000'}),
        }

class BankDetailForm(forms.ModelForm):
    class Meta:
        model = BankDetail
        fields = ['bank_name', 'account_holder', 'account_number', 'ifsc_code', 'is_verified']
        widgets = {
            'bank_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Canara Bank'}),
            'account_holder': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Account holder'}),
            'account_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Account number'}),
            'ifsc_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. CNRB0001234'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

class PFDetailForm(forms.ModelForm):
    class Meta:
        model = PFDetail
        fields = ['pf_number', 'uan_number', 'status']
        widgets = {
            'pf_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'PF Number'}),
            'uan_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'UAN Number'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
        }

class SalaryForm(forms.ModelForm):
    class Meta:
        model = Salary
        fields = ['month', 'base_salary', 'advance_pay', 'deduction', 'overtime_allowance']
        widgets = {
            'month': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'base_salary': forms.NumberInput(attrs={'class': 'form-input'}),
            'advance_pay': forms.NumberInput(attrs={'class': 'form-input'}),
            'deduction': forms.NumberInput(attrs={'class': 'form-input'}),
            'overtime_allowance': forms.NumberInput(attrs={'class': 'form-input'}),
        }
