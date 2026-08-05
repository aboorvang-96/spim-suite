"""Shared helpers for the Projects module.

Kept small so cross-module imports (e.g. from `attendance`) don't drag in
the full view layer just to reuse a couple of write-path utilities.
"""
from django.db.models import F
from django.utils import timezone

from .models import WorkDetailSuggestion


def sites_for_admin(admin_id, restrict_attendance_to=None):
    """Canonical site-name list for a tenant.

    Union of:
      * projects.Site.name for this admin_id (source of truth — its casing wins)
      * attendance.AttendanceRecord.site      (legacy CharField)
      * attendance.AttendanceRecord.site_ref__name

    Case-insensitive dedup; the FIRST casing encountered survives (Projects.Site
    is loaded first so its spelling wins any collision). Sorted A→Z. Blank /
    whitespace-only entries are dropped. Returns list[str].

    `restrict_attendance_to` (date | None) narrows the Attendance contribution
    to that day only. Projects.Site is always included.

    Does NOT read Transaction.location_site or Income.location_site — legacy
    manual-entry values are considered orphans and never resurface here.
    """
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

    try:
        from .models import Site as ProjSite
        for n in (
            ProjSite.objects
            .filter(admin_id=admin_id)
            .values_list('name', flat=True)
        ):
            _add(n)
    except Exception:
        pass

    try:
        from attendance.models import AttendanceRecord
        att = AttendanceRecord.objects.filter(admin_id=admin_id)
        if restrict_attendance_to is not None:
            att = att.filter(date=restrict_attendance_to)
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
