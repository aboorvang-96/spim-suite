from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as Base
from .models import User

@admin.register(User)
class UserAdmin(Base):
    list_display  = ('email', 'username', 'full_name', 'role', 'is_active', 'date_joined')
    list_filter   = ('role', 'is_active')
    search_fields = ('email', 'username', 'full_name')
    ordering      = ('-date_joined',)
    fieldsets = (
        (None,            {'fields': ('email', 'username', 'password')}),
        ('Personal',      {'fields': ('full_name', 'avatar')}),
        ('Role & Access', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Permissions',   {'fields': ('groups', 'user_permissions')}),
    )
    add_fieldsets = ((None, {
        'classes': ('wide',),
        'fields':  ('email', 'username', 'full_name', 'role', 'password1', 'password2'),
    }),)
