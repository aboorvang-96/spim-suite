from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('expenses/', views.api_expenses, name='expenses'),
    path('income/', views.api_income, name='income'),
    path('dashboard/', views.api_dashboard, name='dashboard'),
]
