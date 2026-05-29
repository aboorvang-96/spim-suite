from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

def silent_204(request, *args, **kwargs):
    return HttpResponse(status=204)

urlpatterns = [
    path('admin/',        admin.site.urls),
    path('auth/',         include('accounts.urls',     namespace='accounts')),
    path('dashboard/',    include('dashboard.urls',    namespace='dashboard')),
    path('expenses/',     include('finance.urls',      namespace='expenses')),
    path('finance/',      lambda r: redirect('expenses:list')),
    path('income/',       include('income.urls',       namespace='income')),
    path('transactions/', include('transactions.urls', namespace='transactions')),
    path('projects/',     include('projects.urls',     namespace='projects')),
    path('clients/',      include('clients.urls',      namespace='clients')),
    path('invoices/',     include('invoices.urls',     namespace='invoices')),
    path('employees/',    include('employees.urls',    namespace='employees')),
    path('attendance/',   include('attendance.urls',   namespace='attendance')),
    path('reports/',      include('reports.urls',      namespace='reports')),
    path('branches/',     include('branches.urls',     namespace='branches')),
    path('categories/',   include('categories.urls',   namespace='categories')),
    path('material-stock/', include('material_stock.urls', namespace='material_stock')),
    path('api/',          include('api.urls',          namespace='api')),

    path('offline/', TemplateView.as_view(template_name='pwa/offline.html'), name='offline'),

    path('favicon.ico', silent_204),
    path('.well-known/appspecific/com.chrome.devtools.json', silent_204),
    path('',              lambda r: redirect('accounts:login')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
