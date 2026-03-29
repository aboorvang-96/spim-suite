from django.contrib import admin
from .models import Income


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ['title', 'amount', 'category', 'date', 'source', 'payment_mode', 'user']
    list_filter = ['payment_mode', 'date', 'category']
    search_fields = ['title', 'description', 'source']
