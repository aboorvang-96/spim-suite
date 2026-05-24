from django.urls import path
from . import views
app_name = 'expenses'
urlpatterns = [
    path('',                            views.transaction_list,   name='list'),
    path('add/',                        views.add_transaction,    name='add'),
    path('<int:pk>/edit/',              views.edit_transaction,   name='edit'),
    path('<int:pk>/delete/',            views.delete_transaction, name='delete'),
    path('categories/',                 views.category_list,      name='categories'),
    path('categories/<int:pk>/delete/', views.delete_category,    name='delete_category'),

    # Compat aliases referenced by transactions/list.html AJAX flow
    path('add/',                        views.add_transaction,    name='save_ajax'),
]
