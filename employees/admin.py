"""
Django admin registrations for the employees app.

Kept minimal — registers SalaryStructure (Task 5) so admins have a UI to
manage Role + Level salary configurations without needing a custom template.
"""
from django.contrib import admin
from .models import SalaryStructure


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display    = ('job_role', 'level', 'base_salary', 'food_allowance', 'ot_allowance', 'admin_id')
    list_filter     = ('job_role', 'level', 'admin_id')
    search_fields   = ('job_role__name', 'level', 'admin_id', 'notes')
    ordering        = ('job_role__name', 'level')
    fieldsets = (
        (None, {'fields': ('admin_id', 'job_role', 'level')}),
        ('Salary components', {
            'fields': ('base_salary', 'food_allowance', 'ot_allowance', 'notes'),
        }),
    )
