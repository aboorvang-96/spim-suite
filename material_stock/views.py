"""
Material Stock / Inventory backend views.

Two surfaces:
  - `index`: unchanged — renders the existing template.
  - `state`:
        GET  → returns the full tenant-scoped state (sites, items, entries)
               in the same JSON shape the frontend expects from its three
               localStorage buckets.
        POST → accepts the full state and replaces this tenant's rows
               atomically. Matches the existing JS "save the whole array"
               pattern (preserves UI/UX). Tenant isolation enforced by
               filtering and stamping `admin_id` on every row.

The frontend continues to operate on in-memory arrays; localStorage is
retained as a fast cache, but the backend is now the source of truth.
"""
import json
from datetime import date as date_cls, datetime as datetime_cls
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from accounts.views import get_admin_id
from .models import StockSite, StockItem, StockEntry


@login_required
def index(request):
    return render(request, 'material_stock/index.html')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_decimal(v):
    if v is None or v == '':
        return Decimal('0')
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _to_date(v):
    if not v:
        return None
    if isinstance(v, date_cls):
        return v
    try:
        return datetime_cls.strptime(str(v)[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _to_datetime(v):
    if not v:
        return None
    if isinstance(v, datetime_cls):
        return v
    s = str(v)
    # Accept "YYYY-MM-DDTHH:MM" / "YYYY-MM-DDTHH:MM:SS" / ISO with TZ.
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M',       '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d'):
        try:
            return datetime_cls.strptime(s[:len(fmt) + 6], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _site_to_dict(s):
    return {'id': s.client_id, 'name': s.name}


def _item_to_dict(i):
    return {
        'id':           i.client_id,
        'siteId':       i.site_client_id or '',
        'itemName':     i.item_name,
        'brand':        i.brand,
        'length':       i.length,
        'category':     i.category,
        'qty':          float(i.qty or 0),
        'condition':    i.condition,
    }


def _entry_to_dict(e):
    return {
        'id':              e.client_id,
        'createdAt':       e.created_at.isoformat() if e.created_at else '',
        'updatedAt':       e.updated_at.isoformat() if e.updated_at else '',
        'date':            e.date.isoformat() if e.date else '',
        'fromSite':        e.from_site,
        'toSite':          e.to_site,
        'itemName':        e.item_name,
        'serialNumber':    e.serial_number,
        'typeBrand':       e.type_brand,
        'length':          e.length,
        'quantityOut':     float(e.quantity_out or 0),
        'quantityIn':      float(e.quantity_in or 0),
        'remarks':         e.remarks,
        'workerName':      e.worker_name,
        'dateTime':        e.date_time.isoformat() if e.date_time else '',
        'missingStock':    float(e.missing_stock or 0),
        'damageDeduction': float(e.damage_deduction or 0),
        'approvalBy':      e.approval_by,
    }


# ---------------------------------------------------------------------------
# State endpoint
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['GET', 'POST'])
def state(request):
    admin_id = get_admin_id(request.user)

    if request.method == 'GET':
        sites   = StockSite.objects.filter(admin_id=admin_id)
        items   = StockItem.objects.filter(admin_id=admin_id)
        entries = StockEntry.objects.filter(admin_id=admin_id)
        return JsonResponse({
            'success': True,
            'sites':   [_site_to_dict(s)  for s in sites],
            'items':   [_item_to_dict(i)  for i in items],
            'entries': [_entry_to_dict(e) for e in entries],
        })

    # POST — replace this tenant's full state with the payload.
    try:
        payload = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)

    sites_in   = payload.get('sites')   if 'sites'   in payload else None
    items_in   = payload.get('items')   if 'items'   in payload else None
    entries_in = payload.get('entries') if 'entries' in payload else None

    # Atomic so a half-written sync does not corrupt tenant state.
    with transaction.atomic():
        if isinstance(sites_in, list):
            _replace_sites(admin_id, request.user, sites_in)
        if isinstance(items_in, list):
            _replace_items(admin_id, request.user, items_in)
        if isinstance(entries_in, list):
            _replace_entries(admin_id, request.user, entries_in)

    # Return the canonical post-write snapshot so the client can reconcile.
    sites   = StockSite.objects.filter(admin_id=admin_id)
    items   = StockItem.objects.filter(admin_id=admin_id)
    entries = StockEntry.objects.filter(admin_id=admin_id)
    return JsonResponse({
        'success': True,
        'sites':   [_site_to_dict(s)  for s in sites],
        'items':   [_item_to_dict(i)  for i in items],
        'entries': [_entry_to_dict(e) for e in entries],
    })


# ---------------------------------------------------------------------------
# Replace helpers — keep rows whose client_id is in the payload; insert new
# rows; delete tenant rows no longer present. Tenant isolation is enforced
# at every query because each filter starts with admin_id.
# ---------------------------------------------------------------------------

def _replace_sites(admin_id, user, payload_list):
    incoming_ids = set()
    for raw in payload_list:
        if not isinstance(raw, dict):
            continue
        cid = (raw.get('id') or '').strip()
        if not cid:
            continue
        incoming_ids.add(cid)
        StockSite.objects.update_or_create(
            admin_id=admin_id, client_id=cid,
            defaults={
                'name':       (raw.get('name') or '').strip()[:200],
                'created_by': user if user.is_authenticated else None,
            },
        )
    StockSite.objects.filter(admin_id=admin_id).exclude(client_id__in=incoming_ids).delete()


def _replace_items(admin_id, user, payload_list):
    incoming_ids = set()
    for raw in payload_list:
        if not isinstance(raw, dict):
            continue
        cid = (raw.get('id') or '').strip()
        if not cid:
            continue
        incoming_ids.add(cid)
        StockItem.objects.update_or_create(
            admin_id=admin_id, client_id=cid,
            defaults={
                'site_client_id': (raw.get('siteId') or '').strip()[:80],
                'item_name':      (raw.get('itemName') or '').strip()[:150],
                'brand':          (raw.get('brand') or '').strip()[:150],
                'length':         (raw.get('length') or '').strip()[:50],
                'category':       (raw.get('category') or 'General').strip()[:100],
                'qty':            _to_decimal(raw.get('qty')),
                'condition':      (raw.get('condition') or 'Good').strip()[:50],
                'created_by':     user if user.is_authenticated else None,
            },
        )
    StockItem.objects.filter(admin_id=admin_id).exclude(client_id__in=incoming_ids).delete()


def _replace_entries(admin_id, user, payload_list):
    incoming_ids = set()
    for raw in payload_list:
        if not isinstance(raw, dict):
            continue
        cid = (raw.get('id') or '').strip()
        if not cid:
            continue
        incoming_ids.add(cid)
        StockEntry.objects.update_or_create(
            admin_id=admin_id, client_id=cid,
            defaults={
                'date':             _to_date(raw.get('date')),
                'from_site':        (raw.get('fromSite') or '').strip()[:200],
                'to_site':          (raw.get('toSite')   or '').strip()[:200],
                'item_name':        (raw.get('itemName') or '').strip()[:150],
                'serial_number':    (raw.get('serialNumber') or '').strip()[:100],
                'type_brand':       (raw.get('typeBrand') or '').strip()[:150],
                'length':           (raw.get('length') or '').strip()[:50],
                'quantity_out':     _to_decimal(raw.get('quantityOut')),
                'quantity_in':      _to_decimal(raw.get('quantityIn')),
                'remarks':          (raw.get('remarks') or ''),
                'worker_name':      (raw.get('workerName') or '').strip()[:150],
                'date_time':        _to_datetime(raw.get('dateTime')),
                'missing_stock':    _to_decimal(raw.get('missingStock')),
                'damage_deduction': _to_decimal(raw.get('damageDeduction')),
                'approval_by':      (raw.get('approvalBy') or '').strip()[:150],
                'created_by':       user if user.is_authenticated else None,
            },
        )
    StockEntry.objects.filter(admin_id=admin_id).exclude(client_id__in=incoming_ids).delete()
