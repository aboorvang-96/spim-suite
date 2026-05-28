"""
Django management command: seed_supabase_auth

One-time bootstrap (and optional re-sync) tool: creates or updates Supabase
Auth users for existing employees whose auth_user_id is not yet set.

Day-to-day auto-sync is handled by employees/signals.py — this command is
only needed once (initial bootstrap) or when bulk-updating credentials.

Usage:
    python manage.py seed_supabase_auth
        Create auth users for every active employee that doesn't have one yet.

    python manage.py seed_supabase_auth --dry-run
        Print what would be done without making any changes.

    python manage.py seed_supabase_auth --admin-id ADM26019A
        Restrict to a single tenant.

    python manage.py seed_supabase_auth --update-passwords
        Also update passwords for employees that already have an auth_user_id.
        Use this after a bulk password reset or when re-aligning credentials.

Requirements in .env:
    SUPABASE_URL=https://<project>.supabase.co
    SUPABASE_SERVICE_KEY=<service-role key>    ← NOT the anon key

Synthetic email formula (must match SPIM Lite loginIdToEmail):
    <lower(employee_login_id)>.<lower(admin_id)>@spim.local
    e.g. spim001.adm26019a@spim.local

This email is an internal auth-transport identifier only. It is NEVER stored
in ERP business tables and NEVER shown to employees or admins.
"""

import sys
from django.core.management.base import BaseCommand, CommandError
from employees.models import Employee
from employees.supabase_auth_sync import (
    build_auth_email,
    create_auth_user,
    update_auth_user,
    is_configured,
)


class Command(BaseCommand):
    help = 'Seed (or re-sync) Supabase Auth users for active employees.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be done without making any changes.',
        )
        parser.add_argument(
            '--admin-id',
            dest='admin_id',
            default=None,
            help='Restrict to a single tenant (admin_id value).',
        )
        parser.add_argument(
            '--update-passwords',
            action='store_true',
            dest='update_passwords',
            help='Also update passwords for employees that already have an auth_user_id.',
        )

    def handle(self, *args, **options):
        dry_run          = options['dry_run']
        admin_id_filter  = options.get('admin_id')
        update_passwords = options['update_passwords']

        if not is_configured():
            raise CommandError(
                'SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env. '
                'Use the service-role key (not the anon key).'
            )

        # Base queryset: active employees with a login id and a password to sync.
        qs = Employee.objects.filter(
            mobile_account_active=True,
            employee_login_id__gt='',
            mobile_app_password__gt='',
        )
        if admin_id_filter:
            qs = qs.filter(admin_id=admin_id_filter)

        if not update_passwords:
            # Default: only employees that don't have an auth user yet.
            qs = qs.filter(auth_user_id__isnull=True)

        total = qs.count()
        self.stdout.write(
            f"Found {total} employee(s) to process"
            f"{' (including updates)' if update_passwords else ' (new only)'}."
        )

        if dry_run:
            for emp in qs:
                email  = build_auth_email(emp.employee_login_id, emp.admin_id)
                action = 'update' if emp.auth_user_id else 'create'
                self.stdout.write(
                    f"  [dry-run] would {action} {email}  (employee_id={emp.employee_id})"
                )
            return

        created = updated = skipped = errors = 0
        for emp in qs:
            email  = build_auth_email(emp.employee_login_id, emp.admin_id)
            passwd = emp.mobile_app_password

            if emp.auth_user_id and update_passwords:
                # Update existing auth user's email + password.
                try:
                    update_auth_user(str(emp.auth_user_id), email=email, password=passwd)
                    self.stdout.write(self.style.SUCCESS(
                        f'  UPDATED  {email}  (auth_uid={emp.auth_user_id})'
                    ))
                    updated += 1
                except RuntimeError as exc:
                    self.stderr.write(self.style.ERROR(f'  ERROR updating {email}: {exc}'))
                    errors += 1
            elif not emp.auth_user_id:
                # Create new auth user.
                try:
                    uid = create_auth_user(email, passwd)
                    Employee.objects.filter(pk=emp.pk).update(auth_user_id=uid)
                    self.stdout.write(self.style.SUCCESS(
                        f'  CREATED  {email}  →  auth_user_id={uid}'
                    ))
                    created += 1
                except RuntimeError as exc:
                    msg = str(exc)
                    if 'already been registered' in msg or 'already exists' in msg.lower():
                        self.stdout.write(self.style.WARNING(
                            f'  SKIP  {email} — already in Supabase Auth '
                            f'(run with --update-passwords to resync)'
                        ))
                        skipped += 1
                    else:
                        self.stderr.write(self.style.ERROR(f'  ERROR creating {email}: {exc}'))
                        errors += 1
            else:
                skipped += 1

        self.stdout.write(
            f'\nDone. Created: {created}  Updated: {updated}  '
            f'Skipped: {skipped}  Errors: {errors}'
        )
        if errors:
            sys.exit(1)
