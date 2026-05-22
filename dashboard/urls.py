from django.urls import path
from . import views
app_name = 'dashboard'
urlpatterns = [
    path('', views.index, name='index'),
    path('company/', views.company_settings, name='company_settings'),
    path('api/company-settings/', views.company_settings_json, name='company_settings_json'),
]
