from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('list/', views.employee_list, name='list'),
    path('<int:pk>/', views.employee_detail, name='detail'),
    path('add/', views.add_step1_details, name='add_step1_details'),
    path('<int:pk>/bank/', views.add_step2_bank, name='add_step2_bank'),
    path('<int:pk>/pf/', views.add_step3_pf, name='add_step3_pf'),
    path('<int:pk>/process-salary/', views.process_salary, name='process_salary'),
    path('payslip/<int:salary_id>/', views.view_payslip, name='payslip_view'),
    path('payslip/<int:salary_id>/pdf/', views.download_payslip_pdf, name='payslip_pdf'),
    path('<int:pk>/delete/', views.delete_employee, name='delete'),
    path('manage/', views.manage_employee_ajax, name='manage_ajax'),
    path('', views.salary_manager, name='salary_manager'),
]
