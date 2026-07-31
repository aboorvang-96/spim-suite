"""
SPIM Lite App-Version gate.

Every mobile request sends an `App-Version` header identifying the installed
APK build. This module centralises:

  * `parse_version()`      — tolerant semantic-version parser (MAJOR.MINOR.PATCH).
  * `compare_versions()`   — numeric tuple comparison (never lexicographic).
  * `require_app_version`  — decorator that gates a view behind the version
                             policy in `settings.SPIM_LITE_*`.

Applied to Attendance and Machine Log APIs. Any view lacking the decorator
continues to serve older clients unchanged.

Rejected requests are logged (endpoint, App-Version, employee id when known,
timestamp) on the `spim.api.version` logger. Passwords and bearer tokens are
never touched.
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Optional, Tuple

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone


_log = logging.getLogger('spim.api.version')

FORCE_UPDATE_MESSAGE = (
    "Your SPIM Lite version is no longer supported. "
    "Please install the latest APK."
)


def parse_version(raw: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """
    Parse "MAJOR.MINOR.PATCH" into a (major, minor, patch) int tuple.

    Extra dotted components are ignored (e.g. build metadata). Missing
    components default to 0 so "1" → (1, 0, 0) and "1.2" → (1, 2, 0).
    Returns None when the input is empty or has no valid leading integer.
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None

    parts = s.split('.')
    nums = []
    for part in parts[:3]:
        digits = ''
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            if not nums:
                return None
            break
        nums.append(int(digits))

    if not nums:
        return None
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def compare_versions(a: str, b: str) -> int:
    """Return -1 / 0 / 1 for numeric comparison of two version strings."""
    pa = parse_version(a) or (0, 0, 0)
    pb = parse_version(b) or (0, 0, 0)
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def _force_update_response() -> JsonResponse:
    return JsonResponse(
        {
            'success': False,
            'force_update': True,
            'message': FORCE_UPDATE_MESSAGE,
        },
        status=426,
    )


def _employee_id_for_log(request) -> Optional[str]:
    """
    Best-effort employee identifier for rejection logs. Never touches the
    token string itself; only reads the resolved Employee already attached
    by `mobile_auth_required` when it ran, or looks the token up read-only.
    Returns None when no employee is identifiable.
    """
    emp = getattr(request, 'employee', None)
    if emp is not None:
        return getattr(emp, 'employee_id', None) or str(getattr(emp, 'pk', ''))

    try:
        from .views import _extract_token
        from .models import MobileAuthToken
    except Exception:
        return None

    key = _extract_token(request)
    if not key:
        return None
    try:
        tok = MobileAuthToken.objects.select_related('employee').get(key=key)
    except MobileAuthToken.DoesNotExist:
        return None
    emp = tok.employee
    return getattr(emp, 'employee_id', None) or str(getattr(emp, 'pk', ''))


def require_app_version(view_func):
    """
    Decorator: reject SPIM Lite requests whose App-Version header is missing
    or below `settings.SPIM_LITE_MINIMUM_SUPPORTED_VERSION`.

    Place ABOVE `mobile_auth_required` so unsupported clients never reach
    the auth layer, but the logger will still identify the employee when
    the request carries a valid bearer token.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        # Master kill-switch. When False, every request is allowed through
        # untouched — used while legacy APKs (no App-Version header) are
        # still in the field. Flip settings.SPIM_LITE_ENFORCE_VERSION_GATE
        # back to True once the new versioned APK ships.
        if not getattr(settings, 'SPIM_LITE_ENFORCE_VERSION_GATE', False):
            return view_func(request, *args, **kwargs)

        raw = request.headers.get('App-Version', '')
        minimum = getattr(settings, 'SPIM_LITE_MINIMUM_SUPPORTED_VERSION', '0.0.0')

        # Diagnostic breadcrumb — emitted on EVERY gated request so Railway
        # logs can be grepped for the exact App-Version header the current
        # APK build sends. Once the value is confirmed and the gate is
        # tuned to it, this INFO line can be dropped back to DEBUG or
        # removed entirely.
        _log.info(
            'APP_VERSION_CHECK: endpoint=%s app_version=%s minimum=%s',
            request.path, raw or 'MISSING', minimum,
        )

        parsed = parse_version(raw)
        min_parsed = parse_version(minimum) or (0, 0, 0)

        if parsed is None or parsed < min_parsed:
            _log.warning(
                'SPIM Lite version-gate rejected: endpoint=%s app_version=%s '
                'employee_id=%s minimum=%s ts=%s',
                request.path,
                raw or '<missing>',
                _employee_id_for_log(request) or '<unauthenticated>',
                minimum,
                timezone.now().isoformat(),
            )
            return _force_update_response()

        return view_func(request, *args, **kwargs)
    return _wrapped
