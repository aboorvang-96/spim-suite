from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.index, name='index'),
    path('load/', views.load_attendance, name='load_attendance'),
    path('save/', views.save_attendance, name='save_attendance'),
    path('delete/', views.delete_attendance, name='delete_attendance'),
    path('remarks/unlock/', views.unlock_remarks, name='unlock_remarks'),
]
