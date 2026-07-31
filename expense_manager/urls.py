from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls', namespace='dashboard')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('expenses/', include('expenses.urls', namespace='expenses')),
    path('income/', include('income.urls', namespace='income')),
    path('categories/', include('categories.urls', namespace='categories')),
    path('reports/', include('reports.urls', namespace='reports')),
    path('api/', include('api.urls', namespace='api')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
