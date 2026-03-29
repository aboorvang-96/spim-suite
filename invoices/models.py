from django.db import models
from django.conf import settings

class Invoice(models.Model):
    STATUS = (('draft','Draft'),('sent','Sent'),('paid','Paid'),('overdue','Overdue'))
    invoice_number = models.CharField(max_length=50, unique=True)
    client         = models.ForeignKey('clients.Client', on_delete=models.CASCADE, related_name='invoices')
    project        = models.ForeignKey('projects.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    created_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status         = models.CharField(max_length=10, choices=STATUS, default='draft')
    issue_date     = models.DateField()
    due_date       = models.DateField()
    tax_rate       = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date']

    def __str__(self):
        return self.invoice_number

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())

    @property
    def tax_amount(self):
        return round(self.subtotal * (self.tax_rate / 100), 2)

    @property
    def total(self):
        return self.subtotal + self.tax_amount

class InvoiceItem(models.Model):
    invoice     = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=300)
    quantity    = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    rate        = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def line_total(self):
        return self.quantity * self.rate

    def __str__(self):
        return self.description
