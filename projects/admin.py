from django.contrib import admin
from .models import (
    Project, Task,
    ProjectClient, Site, MachineLocation, WorkStatus,
    WorkLog, WorkDetailSuggestion,
)


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'client', 'owner', 'status', 'start_date', 'due_date')
    inlines      = [TaskInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'priority', 'due_date')


@admin.register(ProjectClient)
class ProjectClientAdmin(admin.ModelAdmin):
    list_display  = ('name', 'admin_id', 'is_active', 'created_at')
    list_filter   = ('is_active', 'admin_id')
    search_fields = ('name',)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display  = ('name', 'client', 'admin_id', 'is_active', 'created_at')
    list_filter   = ('is_active', 'admin_id')
    search_fields = ('name',)
    raw_id_fields = ('client',)


@admin.register(MachineLocation)
class MachineLocationAdmin(admin.ModelAdmin):
    list_display  = ('name', 'site', 'admin_id', 'created_at')
    list_filter   = ('admin_id',)
    search_fields = ('name',)
    raw_id_fields = ('site',)


@admin.register(WorkStatus)
class WorkStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'admin_id', 'created_at')


@admin.register(WorkDetailSuggestion)
class WorkDetailSuggestionAdmin(admin.ModelAdmin):
    list_display  = ('text', 'admin_id', 'usage_count', 'last_used_at')
    list_filter   = ('admin_id',)
    search_fields = ('text',)
