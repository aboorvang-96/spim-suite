"""
One-shot resync for the Attendance → Expense salary sync.

Use when the post_save signal was skipped, errored, or the row was
otherwise missing — the signal handler is called directly for every
AttendanceRecord on/after CUTOVER_DATE, which upserts (or deletes) the
matching finance.Transaction via its idempotent [AUTO-SAL:<pk>] marker.

Safe to run multiple times: update_or_create semantics inside the
signal handler mean no duplicates and no over-write of unrelated rows.

Also doubles as a diagnostic when run with --dry-run: it lists every
attendance row that is currently MISSING its expense mirror.

Examples:
    python manage.py resync_salary_expenses --dry-run
    python manage.py resync_salary_expenses
    python manage.py resync_salary_expenses --admin-id ADM00001
    python manage.py resync_salary_expenses --since 2026-08-01
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.models import AttendanceRecord
from attendance.signals import (
    CUTOVER_DATE,
    _marker,
    sync_expense_from_attendance,
)


class Command(BaseCommand):
    help = "Resync AttendanceRecord rows into their finance.Transaction salary mirrors."

    def add_arguments(self, parser):
        parser.add_argument('--admin-id', default=None,
                            help='Restrict to a single tenant admin_id.')
        parser.add_argument('--since', default=None,
                            help='ISO date (YYYY-MM-DD). Default: CUTOVER_DATE.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Only report which rows are missing; do not write.')

    def handle(self, *args, **opts):
        from finance.models import Transaction

        since = CUTOVER_DATE
        if opts.get('since'):
            since = datetime.date.fromisoformat(opts['since'])

        qs = AttendanceRecord.objects.filter(date__gte=since)
        if opts.get('admin_id'):
            qs = qs.filter(admin_id=opts['admin_id'])

        total = qs.count()
        self.stdout.write(f"Scanning {total} AttendanceRecord rows (since {since}).")

        missing_pks = []
        for att in qs.only('pk', 'admin_id'):
            ref = _marker(att.pk)
            if not Transaction.objects.filter(
                admin_id=att.admin_id, reference=ref, type='expense',
            ).exists():
                missing_pks.append(att.pk)

        self.stdout.write(
            f"Missing expense mirror for {len(missing_pks)} / {total} rows."
        )

        if opts.get('dry_run'):
            for pk in missing_pks[:50]:
                self.stdout.write(f"  att_pk={pk}")
            if len(missing_pks) > 50:
                self.stdout.write(f"  ... (+{len(missing_pks) - 50} more)")
            return

        # Re-drive the signal handler for EVERY row in the window — not
        # just the missing ones — so any drift on amount/site/date/status
        # is corrected too. Handler is idempotent.
        fixed = 0
        started = timezone.now()
        for att in qs.select_related('employee', 'site_ref'):
            try:
                sync_expense_from_attendance(
                    sender=AttendanceRecord, instance=att,
                )
                fixed += 1
            except Exception as exc:
                self.stderr.write(f"  att_pk={att.pk} FAILED: {exc}")

        elapsed = (timezone.now() - started).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"Resynced {fixed} rows in {elapsed:.1f}s."
        ))
