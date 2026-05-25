from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from finance.models import Transaction, Category
from accounts.views import get_admin_id
from branches.models import Branch
from datetime import datetime, timedelta
from django.utils import timezone
import json

@login_required
def transaction_list(request):
    admin_id = get_admin_id(request.user)
    from branches.models import Branch
    import json
    
    # Base Queryset
    qs = Transaction.objects.filter(admin_id=admin_id).select_related('category', 'branch').order_by('-date', '-created_at')
    
    # Serialize for JS State
    tx_list = []
    for t in qs:
        tx_list.append({
            'id': t.id,
            'date': t.date.isoformat(),
            'type': t.type,
            'amount': float(t.amount),
            'desc': t.description or "",
            'catId': t.category_id,
            'catName': t.category.name if t.category else "Uncategorized",
            'catColor': t.category.color if t.category else "#64748b",
            'branchId': t.branch_id,
            'branchName': t.branch.name if t.branch else "Main Office",
            'ref': t.reference or "",
            'vendor': t.vendor or "",
            'mode': t.get_payment_mode_display()
        })

    # Optional: Add Salaries and Incomes from other apps if they aren't in finance.Transaction
    # For now, we assume finance.Transaction is the authoritative source for this view.

    return render(request, 'transactions/list.html', {
        'transactions_json': json.dumps(tx_list),
        'categories': Category.objects.filter(admin_id=admin_id),
        'branches': Branch.objects.filter(admin_id=admin_id),
        'active_transactions': 'active'
    })
