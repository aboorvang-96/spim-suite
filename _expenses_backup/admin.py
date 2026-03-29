from django.contrib import admin
from .models import Expense, Receipt


class ReceiptInline(admin.TabularInline):
    model = Receipt
    extra = 1


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'amount', 'category', 'date', 'payment_method', 'status', 'user']
    list_filter = ['status', 'payment_method', 'date', 'category']
    search_fields = ['title', 'description']
    inlines = [ReceiptInline]


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ['expense', 'file_type', 'uploaded_at']
