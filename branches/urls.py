from django.urls import path
from . import views

app_name = 'branches'
urlpatterns = [
    path('', views.branch_list, name='list'),
    path('manage/', views.manage_branch_ajax, name='manage_ajax'),
    path('<int:pk>/delete/', views.delete_branch_ajax, name='delete_ajax'),
    path('api/locations/', views.locations_api, name='locations_api'),
]
