from django.db import models
from django.conf import settings


class JobRole(models.Model):
    SALARY_TYPE = (
        ('monthly', 'Monthly Salary'),
        ('daily', 'Daily Wage'),
    )
    admin_id    = models.CharField(max_length=20, db_index=True, default='PENDING')
    name        = models.CharField(max_length=150)
    salary_type = models.CharField(max_length=20, choices=SALARY_TYPE, default='monthly')
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = (('admin_id', 'name'),)

    def __str__(self):
        return self.name


class Employee(models.Model):
    STATUS = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
    )
    name                = models.CharField(max_length=150)
    employee_id         = models.CharField(max_length=50, blank=True, default='')
    # Role-level salary configuration (Task 5). `level` is paired with
    # `job_role` to look up a SalaryStructure row that auto-fills the
    # monetary fields below at employee creation time.
    level               = models.CharField(max_length=20, blank=True, default='')
    # Direct-contact and org-grouping fields surfaced in the SPIM Lite profile
    # screen. Kept as plain text to avoid coupling to existing branches.Branch
    # tenant lookups; admins are free to type whatever branch name they use.
    mobile              = models.CharField(max_length=20, blank=True, default='')
    branch              = models.CharField(max_length=100, blank=True, default='')
    # SPIM Lite mobile-app authentication fields
    # mobile_app_password is kept for backward compatibility (admin UI display of
    # the initial generated password). mobile_password_hash is the source of
    # truth for authentication. Once an employee or admin resets the password,
    # mobile_app_password is cleared and only the hash remains.
    mobile_app_password            = models.CharField(max_length=50, blank=True, default='')
    employee_login_id              = models.CharField(max_length=50, blank=True, default='', db_index=True)
    employee_id_edit_count         = models.PositiveSmallIntegerField(default=0)
    mobile_password_hash           = models.CharField(max_length=255, blank=True, default='')
    mobile_password_reset_required = models.BooleanField(default=False)
    mobile_account_active          = models.BooleanField(default=True)
    designation      = models.CharField(max_length=100, blank=True, default='')
    department       = models.CharField(max_length=100, blank=True, default='')
    location         = models.CharField(max_length=100, blank=True, default='')
    site             = models.CharField(max_length=150, blank=True, default='')
    base_salary      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Salary Type selector. 'base_salary' (default) preserves every existing
    # employee's payroll flow byte-for-byte. 'daily_basis' switches the
    # attendance-earnings formula in _compute_attendance_breakdown so
    # `base_salary` is interpreted as a per-day rate multiplied by paid
    # days (see employees/views.py). Non-base fields (OT / Advance /
    # Deductions / PF / Food) continue to work exactly as before.
    SALARY_TYPE_CHOICES = (
        ('base_salary', 'Base Salary'),
        ('daily_basis', 'Daily Basis'),
    )
    salary_type      = models.CharField(
        max_length=20, choices=SALARY_TYPE_CHOICES, default='base_salary',
    )
    # Manual-override flag: False = base_salary follows SalaryStructure(role + level).
    # Flipped to True the moment an admin types a value into Salary Edit that
    # differs from the configured base. Once True, Salary Config updates and
    # role/level changes do NOT overwrite base_salary automatically.
    salary_is_custom_override = models.BooleanField(default=False)
    fixed_allowance  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    joining_date     = models.DateField(blank=True, null=True)
    status           = models.CharField(max_length=15, choices=STATUS, default='active')
    # Supabase Auth uuid. Populated automatically by the post_save signal in
    # employees/signals.py when mobile_app_password is set/changed. Can also
    # be bulk-populated via `python manage.py seed_supabase_auth`. NULL until
    # the first mobile_app_password is saved on this employee.
    auth_user_id     = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    admin_id         = models.CharField(max_length=20, db_index=True, default='PENDING')
    job_role         = models.ForeignKey(JobRole, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    created_by       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='employees_created')
    modified_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='employees_modified')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def has_bank_details(self):
        return hasattr(self, 'bank_details')

    @property
    def has_pf_details(self):
        return hasattr(self, 'pf_details')


class BankDetail(models.Model):
    STATUS = (
        ('verified', 'Verified'),
        ('pending', 'Pending Verification'),
        ('modified', 'Modified after verification'),
    )
    employee       = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='bank_details')
    bank_name      = models.CharField(max_length=150)
    account_holder = models.CharField(max_length=150)
    account_number = models.CharField(max_length=50)
    ifsc_code      = models.CharField(max_length=20)
    branch         = models.CharField(max_length=150, blank=True, default='')
    status         = models.CharField(max_length=20, choices=STATUS, default='pending')
    modified_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='bank_details_modified')
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.bank_name} - {self.employee.name}"


class PFDetail(models.Model):
    STATUS = (
        ('pending', 'Pending Details'),
        ('added', 'Details Added'),
    )
    employee              = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='pf_details')
    pf_number             = models.CharField(max_length=50, blank=True, default='')
    uan_number            = models.CharField(max_length=50, blank=True, default='')
    esic_number           = models.CharField(max_length=50, blank=True, default='')
    status                = models.CharField(max_length=20, choices=STATUS, default='pending')
    employee_contribution = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_contribution = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    joining_date          = models.DateField(blank=True, null=True)
    modified_by           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='pf_details_modified')
    updated_at            = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PF - {self.employee.name}"


class SalaryUpdate(models.Model):
    admin_id             = models.CharField(max_length=20, db_index=True, default='PENDING')
    employee             = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='salary_history')
    month                = models.DateField()
    basic_salary         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    extra_allowance      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ot_allowance         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_pay          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deduction      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay              = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pf_employer_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pf_employee_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    food_allowance       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    food_usage           = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='salaries_created')
    created_at           = models.DateTimeField(auto_now_add=True)
    # Payslip generation lock (Task 4). A SalaryUpdate row holds the payroll
    # numbers as soon as admin processes salary, but the corresponding payslip
    # PDF/HTML download is only released to the employee once admin clicks
    # "Generate Payslip" in the Salary Manager.
    is_payslip_generated  = models.BooleanField(default=False)
    payslip_generated_at  = models.DateTimeField(null=True, blank=True)
    payslip_generated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payslips_generated',
    )

    class Meta:
        verbose_name_plural = 'Salary Updates'
        ordering = ['-month']
        unique_together = (('employee', 'month'),)

    @property
    def food_adjustment(self):
        from decimal import Decimal
        return Decimal(str(self.food_allowance or 0)) - Decimal(str(self.food_usage or 0))

    def __str__(self):
        return f"{self.employee.name} - {self.month.strftime('%B %Y')}"


class EmployeeLevel(models.Model):
    """
    Per-tenant master list of Employee Levels (e.g. L1, L2, L3).

    Used by the Employee Add/Edit dropdown so admins can pre-create levels
    without having to first create a SalaryStructure. Salary configuration
    still uses (job_role + level) as the lookup key; this model simply
    enumerates the level values for the dropdown's "+ Add New" flow.
    """
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    name       = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering        = ['name']
        unique_together = (('admin_id', 'name'),)
        verbose_name        = 'Employee Level'
        verbose_name_plural = 'Employee Levels'

    def __str__(self):
        return self.name


class SalaryStructure(models.Model):
    """
    Role + Level salary configuration (Task 5).

    One row per (admin_id, job_role, level). Used to auto-fill an Employee's
    base_salary, fixed_allowance (food), and ot_allowance at creation when the
    Role + Level pair matches. Existing employees are unaffected; this is a
    lookup, not a runtime calculation.
    """
    admin_id        = models.CharField(max_length=20, db_index=True, default='PENDING')
    job_role        = models.ForeignKey(JobRole, on_delete=models.CASCADE, related_name='salary_structures')
    level           = models.CharField(max_length=20)
    base_salary     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    food_allowance  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ot_allowance    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes           = models.CharField(max_length=250, blank=True, default='')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering        = ['job_role__name', 'level']
        unique_together = (('admin_id', 'job_role', 'level'),)
        verbose_name        = 'Salary Structure'
        verbose_name_plural = 'Salary Structures'

    def __str__(self):
        return f"{self.job_role.name} / {self.level}"
