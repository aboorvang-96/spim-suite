"""Shared helpers for the Projects module.

Kept small so cross-module imports (e.g. from `attendance`) don't drag in
the full view layer just to reuse a couple of write-path utilities.
"""
from django.db.models import F
from django.utils import timezone

from .models import WorkDetailSuggestion


def sites_for_admin(admin_id, restrict_attendance_to=None):
    """Canonical site-name list for a tenant — hard-scoped to TODAY (IST).

    A site name is returned iff EITHER of these hold today (IST):
      * projects.Site row exists for `admin_id` with `is_active=True`, OR
      * attendance.AttendanceRecord exists for `admin_id` on today's date
        whose `site_ref.name` or `site` (CharField) matches.

    Case-insensitive dedup; Projects.Site casing wins collisions (loaded
    first). Sorted A→Z. Blank / whitespace-only entries are dropped.
    Returns list[str].

    `restrict_attendance_to` is accepted for signature compatibility but
    IGNORED — the scope is fixed to today (IST) with no manual override,
    per product spec. Kept in the signature so existing callers keep
    working without churn.

    Does NOT read Transaction.location_site or Income.location_site.
    """
    from accounts.date_utils import today_ist

    today = today_ist()
    canonical = {}

    def _add(name):
        if not name:
            return
        n = name.strip()
        if not n:
            return
        k = n.lower()
        if k not in canonical:
            canonical[k] = n

    # Projects.Site — only rows flagged active. Loaded first so their
    # casing wins any collision with an attendance-only spelling.
    try:
        from .models import Site as ProjSite
        for n in (
            ProjSite.objects
            .filter(admin_id=admin_id, is_active=True)
            .values_list('name', flat=True)
        ):
            _add(n)
    except Exception:
        pass

    # Attendance — TODAY ONLY, both the FK name and the legacy CharField.
    try:
        from attendance.models import AttendanceRecord
        att = AttendanceRecord.objects.filter(admin_id=admin_id, date=today)
        for n in (
            att.exclude(site__isnull=True).exclude(site='')
               .values_list('site', flat=True).distinct()
        ):
            _add(n)
        for n in (
            att.filter(site_ref__isnull=False)
               .values_list('site_ref__name', flat=True).distinct()
        ):
            _add(n)
    except Exception:
        pass

    return sorted(canonical.values(), key=lambda s: s.lower())


def bump_work_detail_suggestion(admin_id, text, user):
    """
    Insert or increment a WorkDetailSuggestion row for `text`.

    Case-insensitive; preserves the first-seen casing. No-op for blanks.
    Best-effort — swallows every exception so a suggestion-corpus hiccup
    can never take down the caller's write path.
    """
    text = (text or '').strip()
    if not text:
        return
    try:
        existing = (
            WorkDetailSuggestion.objects
            .filter(admin_id=admin_id, text__iexact=text)
            .first()
        )
        now = timezone.now()
        if existing:
            WorkDetailSuggestion.objects.filter(pk=existing.pk).update(
                usage_count=F('usage_count') + 1,
                last_used_at=now,
            )
        else:
            WorkDetailSuggestion.objects.create(
                admin_id=admin_id,
                text=text,
                usage_count=1,
                last_used_at=now,
                created_by=user if getattr(user, 'is_authenticated', False) else None,
            )
    except Exception:
        return
