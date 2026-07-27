"""Shared helpers for the Projects module.

Kept small so cross-module imports (e.g. from `attendance`) don't drag in
the full view layer just to reuse a couple of write-path utilities.
"""
from django.db.models import F
from django.utils import timezone

from .models import WorkDetailSuggestion


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
