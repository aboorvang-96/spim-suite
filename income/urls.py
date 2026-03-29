from django.urls import path
from . import views

app_name = 'income'

urlpatterns = [
    path('', views.income_list, name='list'),
    path('add/', views.income_add, name='add'),
    path('<int:pk>/edit/', views.income_edit, name='edit'),
    path('<int:pk>/delete/', views.income_delete, name='delete'),
]
