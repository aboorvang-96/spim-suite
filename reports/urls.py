from django.urls import path
from . import views

app_name = 'reports'
urlpatterns = [
    path('',          views.reports_index,    name='index'),
    path('download/', views.reports_download, name='download'),
]
