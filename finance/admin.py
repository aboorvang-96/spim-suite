from django.contrib import admin
from .models import Category, Transaction, ModuleHiddenSite


@admin.register(ModuleHiddenSite)
class ModuleHiddenSiteAdmin(admin.ModelAdmin):
    list_display  = ('admin_id', 'module', 'site_name', 'hidden_at', 'hidden_by')
    list_filter   = ('module',)
    search_fields = ('admin_id', 'site_name')
    ordering      = ('-hidden_at',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'color', 'created_by')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display   = ('user', 'type', 'amount', 'category', 'date')
    list_filter    = ('type', 'date')
    date_hierarchy = 'date'
