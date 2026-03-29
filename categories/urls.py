from django.urls import path
from . import views

app_name = 'categories'

urlpatterns = [
    # Expense categories
    path('expenses/', views.expense_category_list, name='expense_list'),
    path('expenses/add/', views.expense_category_add, name='expense_add'),
    path('expenses/<int:pk>/edit/', views.expense_category_edit, name='expense_edit'),
    path('expenses/<int:pk>/delete/', views.expense_category_delete, name='expense_delete'),
    # Income categories
    path('income/', views.income_category_list, name='income_list'),
    path('income/add/', views.income_category_add, name='income_add'),
    path('income/<int:pk>/edit/', views.income_category_edit, name='income_edit'),
    path('income/<int:pk>/delete/', views.income_category_delete, name='income_delete'),
]
