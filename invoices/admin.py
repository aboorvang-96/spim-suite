from django.contrib import admin
from .models import Invoice, InvoiceItem

class ItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number','client','status','issue_date','due_date')
    inlines      = [ItemInline]
