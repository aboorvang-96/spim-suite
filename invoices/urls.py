from django.urls import path
from . import views
app_name = 'invoices'
urlpatterns = [
    path('',                 views.invoice_list,   name='list'),
    path('add/',             views.add_invoice,    name='add'),
    path('<int:pk>/',        views.invoice_detail, name='detail'),
    path('<int:pk>/edit/',   views.edit_invoice,   name='edit'),
    path('<int:pk>/delete/', views.delete_invoice, name='delete'),
    path('<int:pk>/paid/',   views.mark_paid,      name='mark_paid'),
]
