from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    # ── Main entry: Work Log Dashboard (replaces bare project list) ──
    path('',                            views.work_log_dashboard,  name='list'),

    # ── [TEMP-DEBUG-WORKLOG-PAGE] admin-only diagnostic — remove after RCA ──
    path('debug/worklog/',              views._debug_worklog,      name='debug_worklog'),

    # ── Work Log CRUD (AJAX) ──
    path('log/',                        views.work_log_dashboard,  name='work_log'),
    path('log/add/',                    views.work_log_add,        name='work_log_add'),
    path('log/upsert/',                 views.work_log_upsert,     name='work_log_upsert'),
    path('log/<int:pk>/edit/',          views.work_log_edit,       name='work_log_edit'),
    path('log/<int:pk>/delete/',        views.work_log_delete,     name='work_log_delete'),
    path('log/<int:pk>/summary-delete/', views.work_log_summary_delete, name='work_log_summary_delete'),
    path('log/<int:pk>/unlock/',        views.work_log_unlock,     name='work_log_unlock'),

    # ── Machine Location & Work Status registry ──
    path('locations/add/',              views.add_machine_location,   name='add_machine_location'),
    path('machines/add/',               views.add_machine_location,   name='add_machine'),
    path('log/status/add/',             views.add_work_status,        name='add_work_status'),

    # ── Projects restructure: Client / Site / Work Details autocomplete ──
    path('clients/add/',                views.add_project_client,     name='add_project_client'),
    path('sites/add/',                  views.add_site,               name='add_site'),
    path('sites/<int:site_id>/move/',   views.move_site,              name='move_site'),
    path('machines/<int:machine_id>/move/', views.move_machine,       name='move_machine'),
    path('clients/<int:client_id>/edit/',     views.edit_project_client,   name='edit_project_client'),
    path('clients/<int:client_id>/delete/',   views.delete_project_client, name='delete_project_client'),
    path('sites/<int:site_id>/edit/',         views.edit_site,             name='edit_site'),
    path('sites/<int:site_id>/delete/',       views.delete_site,           name='delete_site'),
    path('machines/<int:machine_id>/edit/',   views.edit_machine,          name='edit_machine'),
    path('machines/<int:machine_id>/delete/', views.delete_machine,        name='delete_machine'),
    path('work-details/suggest/',       views.work_details_suggest,   name='work_details_suggest'),

    # ── Reports ──
    path('report/machine-monthly/',         views.machine_monthly_report,        name='machine_monthly_report'),
    path('report/machine-monthly/export/',  views.machine_monthly_report_export, name='machine_monthly_report_export'),
    path('machine/<int:machine_id>/history/',          views.machine_history_json,     name='machine_history_json'),
    path('machine/<int:machine_id>/history/download/', views.machine_history_download, name='machine_history_download'),

    # ── Legacy Project / Task routes (preserved for backward compat) ──
    path('projects/add/',               views.add_project,         name='add'),
    path('projects/<int:pk>/',          views.project_detail,      name='detail'),
    path('projects/<int:pk>/edit/',     views.edit_project,        name='edit'),
    path('projects/<int:pk>/delete/',   views.delete_project,      name='delete'),
    path('projects/<int:project_pk>/tasks/add/', views.add_task,   name='add_task'),
    path('tasks/<int:pk>/status/',      views.update_task_status,  name='task_status'),
    path('tasks/<int:pk>/delete/',      views.delete_task,         name='delete_task'),
]
