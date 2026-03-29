from django.urls import path
from . import views
app_name = 'projects'
urlpatterns = [
    path('',                            views.project_list,       name='list'),
    path('add/',                        views.add_project,        name='add'),
    path('<int:pk>/',                   views.project_detail,     name='detail'),
    path('<int:pk>/edit/',              views.edit_project,       name='edit'),
    path('<int:pk>/delete/',            views.delete_project,     name='delete'),
    path('<int:project_pk>/tasks/add/', views.add_task,           name='add_task'),
    path('tasks/<int:pk>/status/',      views.update_task_status, name='task_status'),
    path('tasks/<int:pk>/delete/',      views.delete_task,        name='delete_task'),
]
