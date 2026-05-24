from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    # Primary routes
    path('', views.employee_list, name='list'),
    path('add/', views.add_employee, name='add'),
    path('<int:pk>/edit/', views.edit_employee, name='edit'),
    path('<int:pk>/delete/', views.delete_employee, name='delete'),
    path('<int:pk>/bank/', views.bank_details, name='bank_details'),
    path('<int:pk>/pf/', views.pf_details, name='pf_details'),
    path('<int:pk>/edit/ajax/', views.employee_edit_ajax, name='edit_ajax'),
    path('<int:pk>/salary/', views.salary_management, name='salary_management'),
    path('salary/add/', views.add_salary, name='add_salary'),
    path('export/json/', views.export_json_employees, name='export_json'),
    path('import/excel/', views.import_excel_employees, name='import_excel'),
    path('import/json/', views.import_json_employees, name='import_json'),
    path('payslip/<int:pk>/', views.generate_payslip, name='generate_payslip'),

    # Compatibility aliases — templates reference older wizard-style names.
    # These map to the existing views without changing functionality.
    path('add/', views.add_employee, name='add_step1_details'),
    path('<int:pk>/bank/', views.bank_details, name='add_step2_bank'),
    path('<int:pk>/pf/', views.pf_details, name='add_step3_pf'),
    path('salary/dashboard/', views.salary_dashboard, name='salary_dashboard'),
    path('manage/ajax/', views.manage_ajax, name='manage_ajax'),
    path('salary/generate-expenses/', views.generate_salary_expenses, name='generate_salary_expenses'),
    
    path('<int:pk>/salary/', views.salary_management, name='process_salary'),
    path('<int:pk>/',      views.edit_employee, name='detail'),
    path('salary/dashboard/', views.salary_dashboard, name='salary_manager'),
]
