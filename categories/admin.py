from django.contrib import admin
from .models import ExpenseCategory, IncomeCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_by', 'created_at']
    search_fields = ['name']


@admin.register(IncomeCategory)
class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_by', 'created_at']
    search_fields = ['name']
