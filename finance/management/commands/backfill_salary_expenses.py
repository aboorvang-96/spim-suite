"""One-shot historical backfill: create per-site Salary Expense rows in
finance.Transaction for attendance marked between 2026-07-26 and today_ist().

Run manually (not a migration). Idempotence is provided only by the
UniqueConstraint on reference LIKE 'SAL-%' — a second run for the same
(admin_id, site, today) will fail on that constraint, which is the
intentional guard against accidental double-writes.

Usage:
    python manage.py backfill_salary_expenses --dry-run
    python manage.py backfill_salary_expenses --admin-id ADM12345
    python manage.py backfill_salary_expenses            # writes for all tenants
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction as db_transaction
from django.utils.text import slugify

from accounts.date_utils import today_ist
from attendance.models import AttendanceRecord
from employees.views import compute_daily_salary_for_attendance
from finance.models import Transaction

WINDOW_START = date(2026, 7, 26)


def _resolve_site_name(att):
    """Working-site name for the salary expense row.

    Employee.site is the primary/home site and MUST NOT be used for
    expense attribution — see attendance.site_utils for the rationale.
    Falls back to "OFFICE" (never empty).
    """
    from attendance.site_utils import resolve_working_site
    return resolve_working_site(att)


class Command(BaseCommand):
    help = 'Backfill per-site Salary expense rows from attendance since 2026-07-26.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be created; do not write.',
        )
        parser.add_argument(
            '--admin-id',
            dest='admin_id',
            default=None,
            help='Restrict backfill to a single tenant (admin_id).',
        )

    def handle(self, *args, **opts):
        dry_run = bool(opts.get('dry_run'))
        only_admin = opts.get('admin_id')
        window_end = today_ist()
        booking_date = window_end
        today_stamp = booking_date.strftime('%Y%m%d')

        self.stdout.write(
            f"Window: {WINDOW_START} → {window_end} (inclusive)"
            + (f"  |  admin_id={only_admin}" if only_admin else "  |  all tenants")
            + (f"  |  DRY-RUN" if dry_run else "  |  WRITE")
        )

        qs = (AttendanceRecord.objects
              .filter(date__gte=WINDOW_START, date__lte=window_end)
              .select_related('employee', 'site_ref')
              .order_by('admin_id', 'date', 'id'))
        if only_admin:
            qs = qs.filter(admin_id=only_admin)

        # groups[(admin_id, site_name)] -> dict(amount, employees:set, days:int)
        groups = defaultdict(lambda: {
            'amount':    Decimal('0.00'),
            'employees': set(),
            'days':      0,
        })
        skipped_zero = 0
        errored = 0
        for att in qs.iterator():
            try:
                amt = compute_daily_salary_for_attendance(att)
            except Exception as exc:  # noqa: BLE001
                errored += 1
                self.stderr.write(
                    f"  [ERR] attendance_id={att.id} emp={att.employee_id} "
                    f"date={att.date}: {exc.__class__.__name__}: {exc}"
                )
                continue
            if amt is None or amt <= 0:
                skipped_zero += 1
                continue
            site_name = _resolve_site_name(att)
            key = (att.admin_id, site_name)
            g = groups[key]
            g['amount'] += Decimal(amt)
            g['employees'].add(att.employee_id)
            g['days'] += 1

        # Resolve admin User per tenant (cached).
        User = get_user_model()
        admin_user_by_admin_id = {}
        skipped_tenants = []

        def get_admin_user(admin_id):
            if admin_id in admin_user_by_admin_id:
                return admin_user_by_admin_id[admin_id]
            u = User.objects.filter(admin_id=admin_id, role='admin').first()
            admin_user_by_admin_id[admin_id] = u
            return u

        total_rows_written = 0
        total_amount = Decimal('0.00')
        tenants_seen = set()
        sites_seen = 0
        constraint_conflicts = 0

        for (admin_id, site_name), g in sorted(groups.items()):
            amount = g['amount'].quantize(Decimal('0.01'))
            if amount <= 0:
                continue

            admin_user = get_admin_user(admin_id)
            if admin_user is None:
                if admin_id not in skipped_tenants:
                    skipped_tenants.append(admin_id)
                    self.stderr.write(
                        f"  [WARN] Tenant admin_id={admin_id!r} has no User "
                        f"with role='admin' — SKIPPING all its groups."
                    )
                continue

            site_slug = slugify(site_name) or 'nosite'
            reference = f"SAL-BACKFILL-{admin_id}-{site_slug}-{today_stamp}"
            description = (
                f"Salary backfill {WINDOW_START.strftime('%d %b')} to "
                f"{booking_date.strftime('%d %b %Y')}, "
                f"{len(g['employees'])} employees, {g['days']} attendance days"
            )
            site_display = site_name if site_name else '(No Site)'
            prefix = '[DRY]' if dry_run else '[WRITE]'
            action_line = (
                f"{prefix} [{admin_id}] Site: {site_display} | "
                f"Employees: {len(g['employees'])} | Days: {g['days']} | "
                f"Amount: ₹{amount}"
            )

            if dry_run:
                self.stdout.write(action_line + " → would create")
                tenants_seen.add(admin_id)
                sites_seen += 1
                total_rows_written += 1
                total_amount += amount
                continue

            try:
                with db_transaction.atomic():
                    tx = Transaction.objects.create(
                        user            = admin_user,
                        type            = 'expense',
                        category        = None,
                        expense_category= 'other',
                        amount          = amount,
                        description     = description,
                        date            = booking_date,
                        reference       = reference,
                        location_site   = site_name,
                        purpose         = 'Salary — attendance backfill',
                        payment_mode    = 'cash',
                        admin_id        = admin_id,
                        created_by      = admin_user,
                    )
            except IntegrityError as exc:
                constraint_conflicts += 1
                self.stderr.write(
                    f"  [SKIP] {action_line}  → IntegrityError (likely "
                    f"reference collision from a previous run): {exc}"
                )
                continue

            self.stdout.write(action_line + f" → Expense row created (id={tx.id})")
            tenants_seen.add(admin_id)
            sites_seen += 1
            total_rows_written += 1
            total_amount += amount

        # Grand totals
        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(
            f"{'DRY-RUN SUMMARY' if dry_run else 'BACKFILL SUMMARY'}"
        )
        self.stdout.write("=" * 60)
        self.stdout.write(f"Tenants processed        : {len(tenants_seen)}")
        self.stdout.write(f"Sites (groups) processed : {sites_seen}")
        self.stdout.write(
            f"Expense rows "
            f"{'that would be created' if dry_run else 'created'}       : "
            f"{total_rows_written}"
        )
        self.stdout.write(f"Total amount             : ₹{total_amount}")
        self.stdout.write(f"Zero-amount days skipped : {skipped_zero}")
        if errored:
            self.stdout.write(f"Per-row errors           : {errored}")
        if skipped_tenants:
            self.stdout.write(
                f"Tenants skipped (no admin User): "
                f"{len(skipped_tenants)} — {skipped_tenants}"
            )
        if constraint_conflicts:
            self.stdout.write(
                f"IntegrityError rows skipped: {constraint_conflicts}"
            )
