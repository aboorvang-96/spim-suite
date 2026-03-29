from django.db import models
from django.conf import settings
from django.utils import timezone

class Employee(models.Model):
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    site = models.CharField(max_length=150)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employees')

    def __str__(self):
        return self.name

    @property
    def has_bank_details(self):
        return hasattr(self, 'bank_details')

    @property
    def has_pf_details(self):
        return hasattr(self, 'pf_details')

class BankDetail(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='bank_details')
    bank_name = models.CharField(max_length=150)
    account_holder = models.CharField(max_length=150)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    is_verified = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.bank_name} - {self.employee.name}"

class PFDetail(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='pf_details')
    pf_number = models.CharField(max_length=50, blank=True)
    uan_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('added', 'Added')], default='pending')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PF - {self.employee.name}"

class Salary(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='salaries')
    month = models.DateField()  # Store as first day of month
    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    advance_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Salaries"
        unique_together = ('employee', 'month')
        ordering = ['-month']

    def __str__(self):
        return f"{self.employee.name} - {self.month.strftime('%B %Y')}"

    def calculate_net_pay(self):
        return self.base_salary + self.overtime_allowance - self.advance_pay - self.deduction

    def save(self, *args, **kwargs):
        self.net_pay = self.calculate_net_pay()
        super().save(*args, **kwargs)

class Payslip(models.Model):
    salary = models.OneToOneField(Salary, on_delete=models.CASCADE, related_name='payslip')
    reference_number = models.CharField(max_length=50, unique=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payslip {self.reference_number}"
