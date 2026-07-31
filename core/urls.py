from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/',     admin.site.urls),
    path('auth/',      include('accounts.urls',  namespace='accounts')),
    path('api/',       include('api.urls',       namespace='api')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('finance/',   include('finance.urls',   namespace='finance')),
    path('projects/',  include('projects.urls',  namespace='projects')),
    path('clients/',   include('clients.urls',   namespace='clients')),
    path('invoices/',  include('invoices.urls',  namespace='invoices')),
    path('reports/',   include('reports.urls',   namespace='reports')),
    path('',           lambda r: redirect('accounts:login')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
