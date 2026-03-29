from django.db import models
from django.conf import settings

class Category(models.Model):
    TYPE = (('income', 'Income'), ('expense', 'Expense'))
    name       = models.CharField(max_length=100)
    type       = models.CharField(max_length=10, choices=TYPE)
    color      = models.CharField(max_length=7, default='#6366f1')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='categories')

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['type', 'name']

    def __str__(self):
        return self.name + ' (' + self.get_type_display() + ')'

class Transaction(models.Model):
    TYPE = (('income', 'Income'), ('expense', 'Expense'))
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    type        = models.CharField(max_length=10, choices=TYPE)
    category    = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    amount      = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=300, blank=True)
    date        = models.DateField()
    reference   = models.CharField(max_length=100, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return self.get_type_display() + ' ' + str(self.amount)
