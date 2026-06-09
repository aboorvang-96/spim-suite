"""
One-time cleanup for the duplicate expense rows created by the Expense
Manager site-card Save bug (the inline Save was POSTing to the add endpoint
instead of the edit endpoint, so editing an existing row inserted a new
Transaction instead of updating in place).

This command finds duplicate expense Transactions for the same tenant,
location_site (case-insensitive), and date — keeps the most recently
updated record per group and deletes the rest. It prints a summary of
what would be / was deleted.

Usage:
    python manage.py merge_duplicate_site_expenses                # actually delete
    python manage.py merge_duplicate_site_expenses --dry-run      # report only
    python manage.py merge_duplicate_site_expenses --admin ADM00001
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from finance.models import Transaction


class Command(BaseCommand):
    help = (
        'Merge duplicate expense Transactions that share the same '
        '(admin_id, location_site, date). Keeps the most recently updated '
        'record per group and deletes older duplicates.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be deleted without actually deleting.',
        )
        parser.add_argument(
            '--admin',
            dest='admin_id',
            default=None,
            help='Limit cleanup to a single tenant (admin_id).',
        )

    def handle(self, *args, **options):
        dry_run  = options['dry_run']
        admin_id = options.get('admin_id')

        qs = Transaction.objects.filter(type='expense')
        if admin_id:
            qs = qs.filter(admin_id=admin_id)

        # Group by (admin_id, normalised site, date). The Save-bug duplicate
        # has identical site + date for the same tenant; that's the unique
        # signature we collapse on. Amount is intentionally NOT part of the
        # key because a user editing the amount produces a "duplicate" that
        # differs only in amount.
        buckets = defaultdict(list)
        for t in qs.only('id', 'admin_id', 'location_site', 'date',
                         'amount', 'updated_at', 'created_at'):
            site = (t.location_site or '').strip().lower()
            date = t.date
            key  = (t.admin_id, site, date)
            buckets[key].append(t)

        groups_with_dups = 0
        total_to_delete  = 0
        per_admin_count  = defaultdict(int)
        deletions = []  # list of (kept_id, [deleted_ids])

        for key, items in buckets.items():
            if len(items) < 2:
                continue
            groups_with_dups += 1

            # Most recently updated record wins. updated_at is auto_now and
            # therefore always populated; created_at breaks ties.
            items.sort(
                key=lambda t: (t.updated_at or t.created_at, t.id),
                reverse=True,
            )
            keep, drop = items[0], items[1:]
            total_to_delete += len(drop)
            per_admin_count[key[0]] += len(drop)
            deletions.append((keep, drop, key))

        if not deletions:
            self.stdout.write(self.style.SUCCESS(
                'No duplicate site/date expense rows found. Nothing to do.'
            ))
            return

        # Detailed report.
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            'Duplicate expense rows (same admin_id + site + date):'
        ))
        for keep, drop, key in deletions:
            admin_id_str, site, date = key
            site_disp = site or '(no site)'
            self.stdout.write(
                '  [{admin}] {site} @ {date}  keep id={keep} (₹{amt}, updated {upd})'.format(
                    admin=admin_id_str,
                    site=site_disp,
                    date=date,
                    keep=keep.id,
                    amt=keep.amount,
                    upd=keep.updated_at,
                )
            )
            for t in drop:
                self.stdout.write(
                    '      delete id={id} (₹{amt}, updated {upd})'.format(
                        id=t.id, amt=t.amount, upd=t.updated_at,
                    )
                )

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Summary:'))
        self.stdout.write('  duplicate groups : {}'.format(groups_with_dups))
        self.stdout.write('  rows to delete   : {}'.format(total_to_delete))
        for admin_id_str, n in sorted(per_admin_count.items()):
            self.stdout.write('    {} : {}'.format(admin_id_str, n))

        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'Dry-run mode — no rows were deleted. Re-run without --dry-run to apply.'
            ))
            return

        # Apply deletions in a single transaction so a partial failure
        # doesn't leave the tenant's data half-cleaned.
        ids_to_delete = [t.id for _, drop, _ in deletions for t in drop]
        with transaction.atomic():
            deleted_count, _ = Transaction.objects.filter(id__in=ids_to_delete).delete()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Deleted {} duplicate expense row(s).'.format(deleted_count)
        ))
