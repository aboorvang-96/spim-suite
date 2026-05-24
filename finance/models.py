from django.db import models
from django.conf import settings


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

    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    type         = models.CharField(max_length=10, choices=TYPE)
    category     = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
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
    admin_id     = models.CharField(max_length=20, db_index=True, default='PENDING')
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='transactions_created')
    modified_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='transactions_modified')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return self.get_type_display() + ' ' + str(self.amount)


class Source(models.Model):
    TYPE = (('credit', 'Credit Source'), ('income', 'Income Source'), ('account', 'Account'))
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    name       = models.CharField(max_length=100)
    type       = models.CharField(max_length=10, choices=TYPE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
