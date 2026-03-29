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

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='incomes')
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey(IncomeCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='incomes')
    date = models.DateField()
    source = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='bank_transfer')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.amount}"

    class Meta:
        db_table = 'income'
        ordering = ['-date', '-created_at']
