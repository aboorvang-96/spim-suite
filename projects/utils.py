"""Shared helpers for the Projects module.

Kept small so cross-module imports (e.g. from `attendance`) don't drag in
the full view layer just to reuse a couple of write-path utilities.
"""
from django.db.models import F
from django.utils import timezone

from .models import WorkDetailSuggestion


def sites_for_admin(admin_id, restrict_attendance_to=None):
    """Canonical site-name list for a tenant — scope: current + previous cycle.

    A site name is returned iff EITHER holds:
      * projects.Site row exists for `admin_id` with `is_active=True`, OR
      * attendance.AttendanceRecord exists for `admin_id` in the salary-
        cycle window [previous_cycle.start .. today (IST)], whose
        `site_ref.name` or `site` (CharField) matches.

    Salary cycle: 26th of month N-1 → 25th of month N. On 2026-08-05 the
    current cycle is Jul 26 – Aug 25 and the previous is Jun 26 – Jul 25,
    so the attendance window runs 2026-06-26 → 2026-08-05.

    Case-insensitive dedup; Projects.Site casing wins collisions (loaded
    first). Sorted A→Z. Blank / whitespace-only entries are dropped.
    Returns list[str].

    `restrict_attendance_to` is accepted for signature compatibility but
    IGNORED — the scope is fixed with no manual override, per product spec.

    Does NOT read Transaction.location_site or Income.location_site.
    """
    from datetime import timedelta

    from accounts.date_utils import today_ist
    from accounts.cycle_utils import get_salary_cycle

    today = today_ist()
    # Current cycle contains today. Previous cycle = the one containing
    # (current.start - 1 day), i.e. the 25th of the month before current
    # starts. This derives 'previous' from get_salary_cycle alone; the
    # module's get_previous_cycle is day-insensitive and returns the
    # cycle ending in `today`'s calendar month, which does NOT equal the
    # cycle before the current one for early-month dates.
    current = get_salary_cycle(today)
    previous = get_salary_cycle(current['start'] - timedelta(days=1))
    window_start = previous['start']

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

    # Attendance — window is [previous cycle start .. today], inclusive.
    try:
        from attendance.models import AttendanceRecord
        att = AttendanceRecord.objects.filter(
            admin_id=admin_id,
            date__gte=window_start,
            date__lte=today,
        )
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


def client_sites_for_admin(admin_id):
    """Client/Site rich list for a tenant.

    Union source:
      * projects.Site rows (join to ProjectClient) — active only, source of
        truth for casing.
      * Orphan site names from attendance.AttendanceRecord (site CharField
        or site_ref.name) that don't have a matching projects.Site row —
        client_name defaults to '—', site_id None.

    Case-insensitive dedup on site_name; Projects.Site casing wins. Sorted
    by label. Returns:
        [{'client_name': str, 'site_name': str, 'label': 'CLIENT / SITE',
          'site_id': int|None}, ...]
    """
    from .models import Site as ProjSite

    canonical = {}   # site_name_lower → dict

    try:
        rows = (
            ProjSite.objects
            .filter(admin_id=admin_id, is_active=True)
            .select_related('client')
            .values('id', 'name', 'client__name')
        )
        for r in rows:
            name = (r['name'] or '').strip()
            if not name:
                continue
            key = name.lower()
            if key in canonical:
                continue
            client_name = (r['client__name'] or '—').strip() or '—'
            canonical[key] = {
                'client_name': client_name,
                'site_name':   name,
                'label':       f"{client_name} / {name}",
                'site_id':     r['id'],
            }
    except Exception:
        pass

    try:
        from attendance.models import AttendanceRecord
        att = AttendanceRecord.objects.filter(admin_id=admin_id)
        raw_names = set()
        for n in (
            att.exclude(site__isnull=True).exclude(site='')
               .values_list('site', flat=True).distinct()
        ):
            if n:
                raw_names.add(n.strip())
        for n in (
            att.filter(site_ref__isnull=False)
               .values_list('site_ref__name', flat=True).distinct()
        ):
            if n:
                raw_names.add(n.strip())
        for name in raw_names:
            if not name:
                continue
            key = name.lower()
            if key in canonical:
                continue
            canonical[key] = {
                'client_name': '—',
                'site_name':   name,
                'label':       f"— / {name}",
                'site_id':     None,
            }
    except Exception:
        pass

    return sorted(canonical.values(), key=lambda d: d['label'].lower())


def client_site_label(admin_id, site_name):
    """Return 'CLIENT / SITE' display label for a bare site_name.

    Lookup is case-insensitive against projects.Site rows for this admin.
    Because Site.name is unique per (admin_id, name), one match at most.
    Fallback: '— / SITE' when no Projects.Site row exists.
    """
    name = (site_name or '').strip()
    if not name:
        return ''
    try:
        from .models import Site as ProjSite
        matches = list(
            ProjSite.objects
            .filter(admin_id=admin_id, name__iexact=name)
            .select_related('client')
            .values_list('client__name', 'name')[:2]
        )
        if len(matches) > 1:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "client_site_label: multiple Site rows for admin=%s name=%r",
                admin_id, name,
            )
            return f"Multiple / {name}"
        if matches:
            client_name = (matches[0][0] or '—').strip() or '—'
            display     = (matches[0][1] or name).strip()
            return f"{client_name} / {display}"
    except Exception:
        pass
    return f"— / {name}"


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
