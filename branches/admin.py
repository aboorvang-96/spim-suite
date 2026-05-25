from django.contrib import admin
from .models import Branch, LocationSite

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'manager', 'location', 'created_by')
    search_fields = ('name', 'code', 'manager')

@admin.register(LocationSite)
class LocationSiteAdmin(admin.ModelAdmin):
    list_display  = ('name', 'admin_id', 'created_by', 'created_at')
    search_fields = ('name', 'admin_id')
    list_filter   = ('admin_id',)
