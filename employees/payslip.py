"""
Payslip Generation Module
- Generates formatted payslips with employee, bank, and PF details
- Calculates net pay: Salary + OT - Advance - Deduction
- PF details appear only in payslip (not in salary calculations)
"""

from decimal import Decimal
from datetime import datetime
from django.template.loader import render_to_string
from .models import Employee, SalaryUpdate

class PayslipGenerator:
    def __init__(self, salary_record):
        """
        salary_record: SalaryUpdate instance containing salary data for a specific month
        """
        self.salary = salary_record
        self.employee = salary_record.employee
        self.bank = getattr(self.employee, 'bank_details', None)
        self.pf = getattr(self.employee, 'pf_details', None)

    def calculate_net_pay(self):
        """Return the stored net_pay from the salary record.
        net_pay is computed server-side during salary processing and already
        reflects any attendance-based earnings adjustment, so the payslip
        must use it directly rather than re-deriving from basic_salary."""
        return max(Decimal('0'), Decimal(str(self.salary.net_pay or 0)))

    def get_payslip_data(self):
        """Return all data needed for payslip rendering"""
        net_pay = self.calculate_net_pay()
        
        return {
            # Employee Info
            'employee_name': self.employee.name,
            'employee_id': self.employee.employee_id or '—',
            'designation': self.employee.designation or '—',
            'location': self.employee.location or '—',
            'site': self.employee.site or '—',
            'joining_date': self.employee.joining_date or '—',
            'status': self.employee.get_status_display() if hasattr(self.employee, 'get_status_display') else self.employee.status,
            
            # Bank Details
            'bank_name': self.bank.bank_name if self.bank else '—',
            'account_holder': self.bank.account_holder if self.bank else '—',
            'account_number': self.bank.account_number if self.bank else '—',
            'ifsc_code': self.bank.ifsc_code if self.bank else '—',
            'bank_branch': self.bank.branch if self.bank else '—',
            
            # PF Details (Payslip Only)
            'pf_number': self.pf.pf_number if self.pf else '—',
            'esic_number': self.pf.esic_number if self.pf else '—',
            'uan_number': self.pf.uan_number if self.pf else '—',
            'pf_amount': Decimal(str(self.salary.pf_employee_snapshot or 0)),
            
            # Salary Breakdown
            'month': self.salary.month,
            'basic_salary': Decimal(str(self.salary.basic_salary or 0)),
            'extra_allowance': Decimal(str(self.salary.extra_allowance or 0)),
            'ot_allowance': Decimal(str(self.salary.ot_allowance or 0)),
            'total_earnings': Decimal(str(self.salary.basic_salary or 0)) + Decimal(str(self.salary.extra_allowance or 0)) + Decimal(str(self.salary.ot_allowance or 0)),
            
            # Deductions
            'advance_pay': Decimal(str(self.salary.advance_pay or 0)),
            'total_deduction': Decimal(str(self.salary.total_deduction or 0)),
            'pf_employer': Decimal(str(self.salary.pf_employer_snapshot or 0)),

            # Food Allowance
            'food_allowance': Decimal(str(self.salary.food_allowance or 0)),
            'food_usage': Decimal(str(self.salary.food_usage or 0)),
            'food_adjustment': Decimal(str(self.salary.food_allowance or 0)) - Decimal(str(self.salary.food_usage or 0)),

            # Net Pay
            'net_pay': net_pay,
            'currency': '₹',
            'generated_on': datetime.now(),
        }

    def to_dict(self):
        """Return payslip data as dictionary for JSON/template rendering"""
        return self.get_payslip_data()

    def to_html(self, template_name='employees/payslip.html'):
        """Render payslip as HTML"""
        from django.template.loader import render_to_string
        context = self.get_payslip_data()
        return render_to_string(template_name, context)
