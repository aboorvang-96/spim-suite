from django.urls import path
from . import views

app_name = 'material_stock'

urlpatterns = [
    # ── Pages ────────────────────────────────────────────────────────────
    path('',            views.index,     name='index'),      # Page 1 — Stock (default)
    path('stock/',      views.index,     name='stock'),      # alias for Page 1
    path('master/',     views.master,    name='master'),     # Page 2 — Master Control
    path('movements/',  views.movements, name='movements'),  # Page 3 — Stock In/Out

    # ── Stock report download (PDF / Excel — Page 1) ────────────────────
    path('report/download/', views.stock_report_export, name='stock_report_export'),

    # ── Stock item CRUD ─────────────────────────────────────────────────
    path('api/items/add/',            views.item_add,    name='item_add'),
    path('api/items/<int:pk>/edit/',  views.item_edit,   name='item_edit'),
    path('api/items/<int:pk>/delete/', views.item_delete, name='item_delete'),

    # ── Brand & MaterialType CRUD ───────────────────────────────────────
    path('api/brands/add/',             views.brand_add,    name='brand_add'),
    path('api/brands/<int:pk>/delete/', views.brand_delete, name='brand_delete'),
    path('api/material-types/add/',             views.mtype_add,    name='mtype_add'),
    path('api/material-types/<int:pk>/delete/', views.mtype_delete, name='mtype_delete'),

    # ── Electric Motor catalog CRUD ─────────────────────────────────────
    path('api/motor/add/',             views.motor_add,    name='motor_add'),
    path('api/motor/<int:pk>/edit/',   views.motor_edit,   name='motor_edit'),
    path('api/motor/<int:pk>/delete/', views.motor_delete, name='motor_delete'),

    # ── Movement CRUD ───────────────────────────────────────────────────
    path('api/movements/batch/',           views.movement_batch_add, name='movement_batch_add'),
    path('api/movements/<int:pk>/delete/', views.movement_delete,    name='movement_delete'),

    # ── Site-scoped item lookup + quick-add ─────────────────────────────
    path('api/items-by-site/',   views.items_by_site,  name='items_by_site'),
    path('api/quick-add-item/',  views.quick_add_item, name='quick_add_item'),

    # ── Autocomplete ────────────────────────────────────────────────────
    path('api/persons/suggest/', views.persons_suggest, name='persons_suggest'),
    path('api/sites/suggest/',   views.sites_suggest,   name='sites_suggest'),
    path('api/serials/suggest/', views.serials_suggest, name='serials_suggest'),

    # ── Legacy (retired UI backend, kept so old callers don't 500) ──────
    path('api/state/', views.state, name='state'),
]
