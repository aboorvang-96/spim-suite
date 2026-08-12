"""Rewrite Income.location_site so orphan values (site names not in the
tenant's canonical set from projects.utils.sites_for_admin) collapse to
"OFFICE". Idempotent — a second run is a no-op.

The Add/Edit Income form is intentionally free-form: admins keep typing
sites and new orphans keep appearing over time. This command is the
periodic cleanup pass; the per-site cards on /income/ also fold orphans
into OFFICE at the presentation layer so the display stays correct
between runs.

Flags:
    --dry-run           print what would happen, no writes.
    --admin-id ADMxxxxx scope to one tenant.
"""
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand


OFFICE = 'OFFICE'


class Command(BaseCommand):
    help = (
        "Fold orphan Income.location_site values (not in the canonical "
        "sites_for_admin set) into OFFICE."
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

    def handle(self, *args, **opts):
        from income.models import Income
        from projects.utils import sites_for_admin
        from attendance.site_utils import get_or_create_office_site

        dry_run    = bool(opts.get('dry_run'))
        only_admin = opts.get('admin_id')

        self.stdout.write(
            f"Rewrite Income orphan sites → OFFICE"
            + (f"  |  admin_id={only_admin}" if only_admin else "  |  all tenants")
            + (f"  |  DRY-RUN" if dry_run else "  |  WRITE")
        )

        qs = Income.objects.all()
        if only_admin:
            qs = qs.filter(admin_id=only_admin)

        # Group all rows by admin_id first so we compute the canonical set
        # per tenant exactly once (sites_for_admin is not cheap).
        by_admin = defaultdict(list)
        for row in qs.only('id', 'admin_id', 'location_site', 'amount').iterator():
            by_admin[row.admin_id].append(row)

        inspected = 0
        rewritten = 0
        skipped   = 0
        office_ensured = set()
        pairs = defaultdict(lambda: [0, Decimal('0.00')])  # (old → OFFICE) → [count, amt]

        for admin_id, rows in by_admin.items():
            canonical = {s.lower() for s in sites_for_admin(admin_id)}
            # OFFICE itself is a valid canonical target — never treat an
            # already-OFFICE row as an orphan.
            canonical.add(OFFICE.lower())

            for row in rows:
                inspected += 1
                current = (row.location_site or '').strip()
                if current and current.lower() in canonical:
                    skipped += 1
                    continue

                # Orphan — either blank or a value not in the canonical set.
                display_old = current if current else '(blank)'
                pairs[display_old][0] += 1
                pairs[display_old][1] += Decimal(row.amount or 0)

                self.stdout.write(
                    f"  [REWRITE-INCOME] row={row.id} admin={admin_id} "
                    f"old={display_old!r} → OFFICE amount={row.amount}"
                )

                if not dry_run:
                    if admin_id not in office_ensured:
                        try:
                            get_or_create_office_site(admin_id)
                        except Exception as exc:  # noqa: BLE001
                            self.stderr.write(
                                f"  [WARN] admin={admin_id} could not ensure "
                                f"OFFICE projects.Site: {exc}"
                            )
                        office_ensured.add(admin_id)
                    Income.objects.filter(pk=row.pk).update(location_site=OFFICE)
                rewritten += 1

        self.stdout.write("")
        self.stdout.write("=" * 64)
        self.stdout.write(
            f"{'DRY-RUN SUMMARY' if dry_run else 'REWRITE SUMMARY'}"
        )
        self.stdout.write("=" * 64)
        self.stdout.write(f"Inspected : {inspected}")
        self.stdout.write(f"Rewritten : {rewritten}")
        self.stdout.write(f"Skipped   : {skipped}")
        if pairs:
            self.stdout.write("By (old → OFFICE):")
            for old, (n, amt) in sorted(pairs.items(), key=lambda kv: -kv[1][0]):
                self.stdout.write(f"  {old!r:>40} → OFFICE  rows={n:>5}  amt=₹{amt:>12,.2f}")
        if dry_run:
            self.stdout.write("")
            self.stdout.write("Dry-run only — no writes performed. Re-run without --dry-run to apply.")
