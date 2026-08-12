"""Rewrite finance.Transaction.location_site for salary-derived rows so
they reflect the WORKING site (attendance.site_ref / working_site) instead
of the employee's primary/home site.

Handles three reference shapes:

  a) [AUTO-SAL:{pk}]                — per-day live-sync rows. Look up the
     AttendanceRecord, recompute the working site with the new helper,
     UPDATE location_site in place. Idempotent — a second run is a no-op.

  b) SAL-BACKFILL-%                  — one-shot rows from the old
     backfill_salary_expenses command. No attendance PK is embedded, so
     the correct site is not reconstructible per-row. Log and skip.

  c) SAL-{emp}-{YYYY-MM}             — legacy monthly rows from Path #3
     pre-fix (before the per-site split). DELETE these entirely; the
     rewritten Generate Expenses button regenerates them on demand.
     The newer per-site rows shaped SAL-{emp}-{YYYY-MM}-{site_slug} are
     NOT matched by this rule and are left alone.

Flags:
    --dry-run           print what would happen, no writes.
    --admin-id ADMxxxxx scope to one tenant.
    --since YYYY-MM-DD  default 2026-06-26 (attendance signals CUTOVER_DATE).
"""
import datetime
import re
from collections import defaultdict

from django.core.management.base import BaseCommand

DEFAULT_SINCE = datetime.date(2026, 6, 26)

AUTO_SAL_RE     = re.compile(r'^\[AUTO-SAL:(\d+)\]$')
LEGACY_MONTH_RE = re.compile(r'^SAL-(\d+)-(\d{4}-\d{2})$')


class Command(BaseCommand):
    help = (
        "Rewrite location_site on salary-derived Transaction rows to the "
        "employee's actual WORKING site (attendance.site_ref / working_site)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would change, do not write.',
        )
        parser.add_argument(
            '--admin-id', dest='admin_id', default=None,
            help='Restrict rewrite to a single tenant (admin_id).',
        )
        parser.add_argument(
            '--since', dest='since', default=DEFAULT_SINCE.isoformat(),
            help='Only touch Transactions with date >= this ISO date. '
                 f'Default: {DEFAULT_SINCE.isoformat()}.',
        )

    def handle(self, *args, **opts):
        from finance.models import Transaction
        from attendance.models import AttendanceRecord
        from attendance.site_utils import resolve_working_site

        dry_run   = bool(opts.get('dry_run'))
        only_admin = opts.get('admin_id')
        since_str = opts.get('since') or DEFAULT_SINCE.isoformat()
        try:
            since_date = datetime.date.fromisoformat(since_str)
        except ValueError:
            self.stderr.write(f"Invalid --since value: {since_str!r}")
            return

        self.stdout.write(
            f"Rewrite window: date >= {since_date}"
            + (f"  |  admin_id={only_admin}" if only_admin else "  |  all tenants")
            + (f"  |  DRY-RUN" if dry_run else "  |  WRITE")
        )

        # Match all three shapes with a startswith prefix set — cheaper
        # than an OR of icontains and correct enough because each shape
        # has a stable leading token.
        base_qs = Transaction.objects.filter(
            type='expense',
            date__gte=since_date,
        )
        if only_admin:
            base_qs = base_qs.filter(admin_id=only_admin)

        auto_qs = base_qs.filter(reference__startswith='[AUTO-SAL:')
        backfill_qs = base_qs.filter(reference__startswith='SAL-BACKFILL-')
        sal_month_qs = (
            base_qs.filter(reference__startswith='SAL-')
                   .exclude(reference__startswith='SAL-BACKFILL-')
        )

        # ---- (a) [AUTO-SAL:pk] ------------------------------------------
        auto_inspected = 0
        auto_rewritten = 0
        auto_skipped   = 0
        auto_orphans   = 0
        rewrite_pairs  = defaultdict(int)  # (old, new) -> count

        # Preload attendance rows in batches by extracted pk.
        pk_to_txn = {}
        for tx in auto_qs.iterator():
            auto_inspected += 1
            m = AUTO_SAL_RE.match(tx.reference or '')
            if not m:
                auto_skipped += 1
                continue
            att_pk = int(m.group(1))
            pk_to_txn.setdefault(att_pk, []).append(tx)

        att_map = {}
        if pk_to_txn:
            for att in (AttendanceRecord.objects
                        .filter(pk__in=list(pk_to_txn.keys()))
                        .select_related('site_ref')
                        .iterator()):
                att_map[att.pk] = att

        for att_pk, txns in pk_to_txn.items():
            att = att_map.get(att_pk)
            if att is None:
                auto_orphans += len(txns)
                for tx in txns:
                    self.stdout.write(
                        f"  [WARN] orphan AUTO-SAL: txn={tx.id} "
                        f"ref={tx.reference} — AttendanceRecord {att_pk} missing"
                    )
                continue
            new_site = resolve_working_site(att)
            for tx in txns:
                old_site = tx.location_site or ''
                if (old_site or '').strip() == (new_site or '').strip():
                    auto_skipped += 1
                    continue
                rewrite_pairs[(old_site or '(empty)', new_site)] += 1
                self.stdout.write(
                    f"  [REWRITE] txn={tx.id} attendance={att.pk} "
                    f"old={old_site!r} new={new_site!r}"
                )
                if not dry_run:
                    tx.location_site = new_site
                    tx.save(update_fields=['location_site'])
                auto_rewritten += 1

        # ---- (b) SAL-BACKFILL-% -----------------------------------------
        backfill_inspected = 0
        backfill_skipped   = 0
        for tx in backfill_qs.iterator():
            backfill_inspected += 1
            backfill_skipped += 1
            self.stdout.write(
                f"  [SKIP-BACKFILL] txn={tx.id} ref={tx.reference} "
                f"site={tx.location_site!r} amount={tx.amount} "
                "— no attendance PK embedded; user must decide."
            )

        # ---- (c) SAL-{emp}-{YYYY-MM} (legacy monthly, pre-split) --------
        legacy_inspected = 0
        legacy_deleted   = 0
        legacy_kept      = 0
        for tx in sal_month_qs.iterator():
            legacy_inspected += 1
            m = LEGACY_MONTH_RE.match(tx.reference or '')
            if not m:
                # e.g. new per-site shape SAL-{emp}-{YYYY-MM}-{slug} — leave.
                legacy_kept += 1
                continue
            emp_pk, month_slug = m.group(1), m.group(2)
            self.stdout.write(
                f"  [DELETE] txn={tx.id} emp={emp_pk} month={month_slug} "
                f"amount={tx.amount} old_site={tx.location_site!r}"
            )
            if not dry_run:
                tx.delete()
            legacy_deleted += 1

        # ---- Summary ----------------------------------------------------
        self.stdout.write("")
        self.stdout.write("=" * 64)
        self.stdout.write(
            f"{'DRY-RUN SUMMARY' if dry_run else 'REWRITE SUMMARY'}"
        )
        self.stdout.write("=" * 64)
        self.stdout.write("(a) [AUTO-SAL:pk] per-day rows")
        self.stdout.write(f"    inspected : {auto_inspected}")
        self.stdout.write(f"    rewritten : {auto_rewritten}")
        self.stdout.write(f"    skipped   : {auto_skipped}")
        self.stdout.write(f"    orphans   : {auto_orphans}")
        if rewrite_pairs:
            self.stdout.write("    by (old → new):")
            for (old, new), n in sorted(
                rewrite_pairs.items(), key=lambda kv: -kv[1]
            ):
                self.stdout.write(f"      {old!r:>30} → {new!r:<30} : {n}")
        self.stdout.write("")
        self.stdout.write("(b) SAL-BACKFILL-% one-shot rows")
        self.stdout.write(f"    inspected : {backfill_inspected}")
        self.stdout.write(f"    skipped   : {backfill_skipped}  (no attendance PK)")
        self.stdout.write("")
        self.stdout.write("(c) SAL-{emp}-{YYYY-MM} legacy monthly rows")
        self.stdout.write(f"    inspected : {legacy_inspected}")
        self.stdout.write(f"    deleted   : {legacy_deleted}")
        self.stdout.write(f"    kept      : {legacy_kept}  (per-site shape, left alone)")
        if dry_run:
            self.stdout.write("")
            self.stdout.write("Dry-run only — no writes performed. Re-run without --dry-run to apply.")
