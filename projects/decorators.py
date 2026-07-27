from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """
    Gate a view to users whose role is admin/super_admin.
    Matches the `User.is_admin` property in accounts/models.py.

    - XHR / JSON callers get a 403 JSON body so fetch()s can surface the error.
    - Regular page requests are redirected to the dashboard with a flash message.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not getattr(request.user, 'is_admin', False):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' \
               or request.content_type == 'application/json':
                return JsonResponse(
                    {'success': False, 'error': 'Admin permission required.'},
                    status=403,
                )
            messages.error(request, 'Admin permission required.')
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return _wrapped
