from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Legacy (kept for backward compatibility — not actively used)
    path('expenses/',  views.api_expenses,  name='expenses'),
    path('income/',    views.api_income,    name='income'),
    path('dashboard/', views.api_dashboard, name='dashboard'),

    # SPIM Lite mobile endpoints
    path('mobile/login/',           views.mobile_login,           name='mobile_login'),
    path('mobile/logout/',          views.mobile_logout,          name='mobile_logout'),
    path('mobile/change-password/', views.mobile_change_password, name='mobile_change_password'),
    path('mobile/reset-password/',  views.mobile_reset_password,  name='mobile_reset_password'),
    path('mobile/profile/',                  views.mobile_profile,           name='mobile_profile'),
    path('mobile/attendance/',               views.mobile_attendance,        name='mobile_attendance'),
    path('mobile/payslips/',                 views.mobile_payslips,          name='mobile_payslips'),
    path('mobile/payslips/<int:pk>/download/', views.mobile_payslip_download, name='mobile_payslip_download'),
    path('mobile/worklogs/',                 views.mobile_worklogs,          name='mobile_worklogs'),
    path('mobile/machines/',                 views.mobile_machines,          name='mobile_machines'),
    path('mobile/sites/',                    views.mobile_sites,             name='mobile_sites'),
    path('mobile/bank-details/',             views.mobile_bank_details,      name='mobile_bank_details'),
    path('mobile/salary/',                   views.mobile_salary,            name='mobile_salary'),
    path('mobile/dashboard/',                views.mobile_dashboard,         name='mobile_dashboard'),

    # SPIM Lite HR-only mobile endpoints (read-only, tenant-scoped)
    path('mobile/hr/employees/',   views.mobile_hr_employees,  name='mobile_hr_employees'),
    path('mobile/hr/attendance/',  views.mobile_hr_attendance, name='mobile_hr_attendance'),
    path('mobile/hr/salary/',      views.mobile_hr_salary,     name='mobile_hr_salary'),

    # HR Income CRUD — read/write, tenant-scoped, HR-gated.
    path('mobile/hr/income/categories/', views.mobile_hr_income_categories, name='mobile_hr_income_categories'),
    path('mobile/hr/income/',            views.mobile_hr_income_list,       name='mobile_hr_income_list'),
    path('mobile/hr/income/<int:pk>/',   views.mobile_hr_income_detail,     name='mobile_hr_income_detail'),

    # HR Expense CRUD — read/write, tenant-scoped, HR-gated.
    path('mobile/hr/expense/categories/', views.mobile_hr_expense_categories, name='mobile_hr_expense_categories'),
    path('mobile/hr/expense/',            views.mobile_hr_expense_list,       name='mobile_hr_expense_list'),
    path('mobile/hr/expense/<int:pk>/',   views.mobile_hr_expense_detail,     name='mobile_hr_expense_detail'),

    # HR Attendance Report — PDF / XLSX download, tenant-scoped, HR-gated.
    path('mobile/hr/attendance/report/',  views.mobile_hr_attendance_report,  name='mobile_hr_attendance_report'),

    # HR Income Report — PDF / XLSX download, tenant-scoped, HR-gated.
    path('mobile/hr/income/report/',      views.mobile_hr_income_report,      name='mobile_hr_income_report'),

    # HR Expense Report — PDF / XLSX download, tenant-scoped, HR-gated.
    path('mobile/hr/expense/report/',     views.mobile_hr_expense_report,     name='mobile_hr_expense_report'),

    # HR Dashboard — aggregated today's attendance summary, HR-gated.
    path('mobile/hr/dashboard/today/',    views.mobile_hr_dashboard_today,    name='mobile_hr_dashboard_today'),
]
