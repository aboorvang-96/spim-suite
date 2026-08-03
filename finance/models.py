from django.db import models
from django.db.models import Q
from django.conf import settings
from accounts.date_utils import validate_not_future


class Category(models.Model):
    TYPE = (('income', 'Income'), ('expense', 'Expense'))
    name        = models.CharField(max_length=100)
    type        = models.CharField(max_length=10, choices=TYPE)
    color       = models.CharField(max_length=7, default='#6366f1')
    admin_id    = models.CharField(max_length=20, db_index=True, default='PENDING')
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='categories_created')
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='categories_modified')
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['type', 'name']

    def __str__(self):
        return self.name + ' (' + self.get_type_display() + ')'


class Transaction(models.Model):
    TYPE = (('income', 'Income'), ('expense', 'Expense'))
    PAYMENT_MODE = (
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI/Online'),
    )

    # Fixed-choice category for the site-based Expense view (Income/Expense
    # restructure). Distinct from the flexible Category FK below so existing
    # category data is preserved — this enum is only read/written by the
    # site-grouped Expense detail panel and its Add/Edit modal.
    EXPENSE_CATEGORY_CHOICES = (
        ('food',   'Food'),
        ('fuel',   'Fuel'),
        ('ticket', 'Ticket'),
        ('travel', 'Travel'),
        ('other',  'Other/Misc'),
    )

    # Provenance of an expense row — what created it and, by extension, how
    # it should be labelled / grouped on the Expense page.
    SOURCE_CHOICES = (
        ('manual',            'Manual'),
        ('salary_attendance', 'Salary — Attendance'),
        ('salary_payslip',    'Salary — Payslip'),
        ('material',          'Material'),
        ('other',             'Other'),
    )

    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    type         = models.CharField(max_length=10, choices=TYPE)
    category     = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    # New fixed-choice category for the site-based Expense detail panel.
    expense_category = models.CharField(max_length=20, choices=EXPENSE_CATEGORY_CHOICES, blank=True, default='')
    amount       = models.DecimalField(max_digits=12, decimal_places=2)
    description  = models.CharField(max_length=300, blank=True)
    date         = models.DateField()
    time         = models.TimeField(blank=True, null=True)
    reference    = models.CharField(max_length=100, blank=True)
    vendor       = models.CharField(max_length=200, blank=True, null=True)
    location_site = models.CharField(max_length=200, blank=True, null=True)
    purpose      = models.CharField(max_length=300, blank=True, null=True)
    payment_by   = models.CharField(max_length=100, blank=True, null=True)
    payment_mode  = models.CharField(max_length=20, choices=PAYMENT_MODE, default='cash')
    income_source = models.CharField(max_length=200, blank=True, default='')
    attachment    = models.FileField(upload_to='receipts/', blank=True, null=True)
    branch       = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')

    # Site-based Expense view (Income/Expense restructure — 2026-08). The
    # location_site CharField above stays as the legacy free-text field the
    # existing card view groups on; the new site FK is populated alongside
    # for new writes so grouping can migrate from string to FK gradually.
    site         = models.ForeignKey(
        'projects.Site', on_delete=models.PROTECT,
        null=True, blank=True, related_name='finance_transactions',
    )
    source       = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='manual', db_index=True,
    )
    # Salary-source rows point back to the Employee (and, for per-day rows
    # driven by attendance, to the AttendanceRecord). CASCADE on attendance
    # so deleting an attendance auto-removes its salary_attendance expense.
    employee     = models.ForeignKey(
        'employees.Employee', on_delete=models.PROTECT,
        null=True, blank=True, related_name='transaction_entries',
    )
    attendance_record = models.ForeignKey(
        'attendance.AttendanceRecord', on_delete=models.CASCADE,
        null=True, blank=True, related_name='transaction_entries',
    )
    breakdown_note = models.CharField(max_length=300, blank=True, default='')

    admin_id     = models.CharField(max_length=20, db_index=True, default='PENDING')
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='transactions_created')
    modified_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='transactions_modified')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        constraints = [
            # DB-level dedup for the auto-generated salary payout rows keyed
            # on reference = "SAL-{employee_pk}-{YYYY-MM}". Prevents concurrent
            # generate_salary_expenses calls from racing past the app-level
            # exists() check and inserting duplicate salary expenses. Scoped
            # to 'SAL-' references so it does not constrain any unrelated
            # transactions that share a reference string.
            models.UniqueConstraint(
                fields=['admin_id', 'reference', 'type'],
                condition=Q(reference__startswith='SAL-'),
                name='unique_salary_transaction_ref',
            ),
            # One expense row per AttendanceRecord (per tenant). Guards the
            # attendance→expense signal against duplicate inserts if a race
            # slips past update_or_create's SELECT.
            models.UniqueConstraint(
                fields=['admin_id', 'attendance_record'],
                condition=Q(attendance_record__isnull=False),
                name='unique_tx_per_attendance',
            ),
        ]

    def __str__(self):
        return self.get_type_display() + ' ' + str(self.amount)

    def clean(self):
        super().clean()
        validate_not_future(self.date, "Transaction date")

    def save(self, *args, **kwargs):
        validate_not_future(self.date, "Transaction date")
        super().save(*args, **kwargs)


class Source(models.Model):
    TYPE = (('credit', 'Credit Source'), ('income', 'Income Source'), ('account', 'Account'))
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    name       = models.CharField(max_length=100)
    type       = models.CharField(max_length=10, choices=TYPE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
