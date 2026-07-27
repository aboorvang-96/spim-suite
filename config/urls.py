import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, Http404
from django.shortcuts import redirect
from django.views.generic import TemplateView
from projects.views import work_details_suggest as _projects_work_details_suggest

def silent_204(request, *args, **kwargs):
    return HttpResponse(status=204)


def serve_service_worker(request):
    """
    Serve the PWA Service Worker at the root URL `/sw.js` so it can claim
    scope `/`.

    A Service Worker can only claim a scope at-or-below its own URL path.
    The file's source lives at `static/pwa/sw.js`, so if the browser fetched
    it from `/static/pwa/sw.js` the natural scope would be `/static/pwa/`
    and registering with `{ scope: '/' }` would raise:
        SecurityError: The path of the provided scope ('/') is not under
        the max scope allowed ('/static/pwa/')

    Serving the same bytes from `/sw.js` lets the SW claim scope `/` —
    the standard PWA pattern. We also emit `Service-Worker-Allowed: /` as
    a defensive belt-and-suspenders header and `Cache-Control: no-cache`
    so future SW updates propagate to clients on the next visit.
    """
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'pwa', 'sw.js')
    try:
        with open(sw_path, 'rb') as f:
            content = f.read()
    except FileNotFoundError:
        raise Http404('Service worker file not found')
    response = HttpResponse(content, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response

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

    # Alias for the desktop autocomplete — same view, spec-literal path
    # so external callers can hit /api/projects/work-details/suggest/.
    path('api/projects/work-details/suggest/', _projects_work_details_suggest,
         name='api_work_details_suggest'),

    path('offline/', TemplateView.as_view(template_name='pwa/offline.html'), name='offline'),

    # Root-served Service Worker so it can claim scope '/' — see view docstring.
    path('sw.js', serve_service_worker, name='service_worker'),

    path('favicon.ico', silent_204),
    path('.well-known/appspecific/com.chrome.devtools.json', silent_204),
    path('',              lambda r: redirect('accounts:login')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
