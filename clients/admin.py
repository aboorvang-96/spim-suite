from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display  = ('name','company','email','phone','added_by')
    search_fields = ('name','company','email')
