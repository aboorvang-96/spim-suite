from django.db import models
from django.conf import settings
from categories.models import IncomeCategory


class Income(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('upi', 'UPI'),
        ('online', 'Online'),
        ('other', 'Other'),
    ]

    user     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='incomes')
    admin_id = models.CharField(max_length=20, db_index=True, default='PENDING')
    title    = models.CharField(max_length=200, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey(IncomeCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='incomes')
    date = models.DateField()
    source = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='bank_transfer')
    income_type = models.CharField(max_length=100, blank=True, default='')
    location_site = models.CharField(max_length=200, blank=True, default='')
    payment_by = models.CharField(max_length=200, blank=True, default='')
    # New fields for site-based Income view (Income/Expense restructure).
    # `from_account` / `to_account` model the "From Account" / "To Account"
    # columns in the site detail panel — they sit alongside (not replacing)
    # the existing `payment_mode` "Account" field. `remarks` is a short
    # note shown in the detail panel separately from `description`, which
    # remains the longer free-text "Notes / Remarks" body.
    from_account = models.CharField(max_length=200, blank=True, default='')
    to_account   = models.CharField(max_length=200, blank=True, default='')
    remarks      = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.amount}"

    class Meta:
        db_table = 'income'
        ordering = ['-date', '-created_at']
