from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json as _json
from .models import Branch, LocationSite
from accounts.views import is_admin_user, get_admin_id


def _sync_location(admin_id, name, user):
    """Register a location/site string in the centralized table if not already present."""
    name = (name or '').strip()
    if not name:
        return
    if not LocationSite.objects.filter(admin_id=admin_id, name__iexact=name).exists():
        LocationSite.objects.create(admin_id=admin_id, name=name, created_by=user)


@login_required
def locations_api(request):
    """
    GET  /branches/api/locations/  — list all centralized locations for this tenant.
    POST /branches/api/locations/  — add a new location (case-insensitive dedup).
    """
    admin_id = get_admin_id(request.user)

    if request.method == 'GET':
        names = list(
            LocationSite.objects.filter(admin_id=admin_id).values_list('name', flat=True)
        )
        return JsonResponse({'locations': names})

    if request.method == 'POST':
        try:
            data = _json.loads(request.body)
            name = (data.get('name') or '').strip()
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            _sync_location(admin_id, name, request.user)
            names = list(
                LocationSite.objects.filter(admin_id=admin_id).values_list('name', flat=True)
            )
            return JsonResponse({'success': True, 'locations': names})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def branch_list(request):
    admin_id = get_admin_id(request.user)
    branches = Branch.objects.filter(admin_id=admin_id)

    from django.db.models import Count, Sum, Q
    from finance.models import Transaction  # noqa: F401 (used via related_name annotation)

    branches = branches.annotate(
        txn_count    = Count('transactions'),
        total_income = Sum('transactions__amount', filter=Q(transactions__type='income')),
        total_expense= Sum('transactions__amount', filter=Q(transactions__type='expense')),
    )

    branch_list = []
    for b in branches:
        branch_list.append({
            'id': b.id, 'name': b.name, 'code': b.code or '',
            'location': b.location or '', 'manager': b.manager or '', 'note': b.note or '',
            'txnCount': b.txn_count or 0,
            'income':   float(b.total_income  or 0),
            'expense':  float(b.total_expense or 0),
        })

    location_names = list(
        LocationSite.objects.filter(admin_id=admin_id).values_list('name', flat=True)
    )
    return render(request, 'branches/list.html', {
        'branches_json':       _json.dumps(branch_list),
        'location_sites_json': _json.dumps(location_names),
        'active_branches':     'active',
    })

@login_required
def manage_branch_ajax(request):
    if request.method == 'POST':
        try:
            data = _json.loads(request.body)
            b_id = data.get('id')
            if b_id:
                b = Branch.objects.get(id=b_id, admin_id=get_admin_id(request.user))
            else:
                b = Branch(created_by=request.user)
            b.name     = data.get('name', '')
            b.code     = data.get('code', '')
            b.location = data.get('location', '')
            b.manager  = data.get('manager', '')
            b.note     = data.get('note', '')
            b.admin_id = get_admin_id(request.user)
            b.save()
            # Sync the COMBINED "Branch Name / Location" to the centralized list.
            # Primary format: "Name / Location". Fallback to whichever part exists.
            admin_id = get_admin_id(request.user)
            loc  = (b.location or '').strip()
            name = (b.name or '').strip()
            if name and loc:
                _sync_location(admin_id, f"{name} / {loc}", request.user)
            elif name:
                _sync_location(admin_id, name, request.user)
            elif loc:
                _sync_location(admin_id, loc, request.user)
            return JsonResponse({'success': True, 'id': b.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def delete_branch_ajax(request, pk):
    if request.method == 'POST':
        try:
            b = get_object_or_404(Branch, pk=pk, admin_id=get_admin_id(request.user))
            b.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})
