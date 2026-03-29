from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.employee_list, name='list'),
    path('add/', views.add_employee, name='add'),
    path('<int:pk>/edit/', views.edit_employee, name='edit'),
    path('<int:pk>/delete/', views.delete_employee, name='delete'),
    path('<int:pk>/bank/', views.bank_details, name='bank_details'),
    path('<int:pk>/pf/', views.pf_details, name='pf_details'),
    path('<int:pk>/salary/', views.salary_management, name='salary_management'),
    path('salary/add/', views.add_salary, name='add_salary'),
    path('payslip/<int:pk>/', views.generate_payslip, name='generate_payslip'),
]
