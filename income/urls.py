from django.urls import path
from . import views

app_name = 'income'

urlpatterns = [
    path('', views.income_list, name='list'),
    path('add/', views.income_add, name='add'),
    path('export/csv/', views.income_export_csv, name='export_csv'),
    path('<int:pk>/edit/', views.income_edit, name='edit'),
    path('<int:pk>/delete/', views.income_delete, name='delete'),
    path('bulk-delete-by-sites/', views.delete_incomes_by_sites, name='delete_incomes_by_sites'),
    path('debug-site-match/',     views.debug_site_match_income, name='debug_site_match'),
    path('api/sources/', views.shared_sources_api, name='sources_api'),
    path('api/accounts/', views.shared_accounts_api, name='accounts_api'),
]
