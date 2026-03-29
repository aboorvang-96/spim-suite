from django.contrib import admin
from .models import Category, Transaction

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'color', 'created_by')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display   = ('user', 'type', 'amount', 'category', 'date')
    list_filter    = ('type', 'date')
    date_hierarchy = 'date'
