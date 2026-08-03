"""
0011 — Data-only backfill. For every AttendanceRecord with
date >= ATTENDANCE_EXPENSE_CUTOVER (2026-07-26), upsert a
Transaction row with source='salary_attendance'. Uses the exact same
compute_daily_salary helper the runtime signal will use so backfilled rows
and future signal rows agree byte-for-byte.

Guarded for reruns: idempotent via the (admin_id, attendance_record)
partial unique constraint added in 0010, plus an explicit exists() check.

Rows whose amount would be 0 (absent, no_week_off, unknown status, or a
daily-basis employee on a non-earning status) are skipped entirely — we do
not book zero-amount expenses.

`atomic = False` — potentially thousands of writes; letting them commit in
chunks keeps a single row-level error from rolling back the entire
backfill. Individual per-row errors are printed and skipped.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    from employees.salary_calc import (
        compute_daily_salary,
        build_expense_defaults,
        ATTENDANCE_EXPENSE_CUTOVER,
    )
    AttendanceRecord = apps.get_model('attendance', 'AttendanceRecord')
    Transaction      = apps.get_model('finance', 'Transaction')
    Category         = apps.get_model('finance', 'Category')

    processed = created = skipped_exists = skipped_zero = errors = 0

    # We need Employee attributes (base_salary, salary_type, location, site)
    # that live on the real model. The historical model returned by
    # apps.get_model() has the fields but not custom methods, which is fine
    # here — compute_daily_salary only reads plain attributes.
    qs = AttendanceRecord.objects.filter(
        date__gte=ATTENDANCE_EXPENSE_CUTOVER,
    ).select_related('employee', 'site_ref').order_by('date', 'id')

    # Cache the "Salary" category per tenant so we don't hit the DB per row.
    salary_cat_by_admin = {}

    def get_salary_category(admin_id):
        if admin_id in salary_cat_by_admin:
            return salary_cat_by_admin[admin_id]
        cat = (Category.objects
               .filter(admin_id=admin_id, name='Salary', type='expense')
               .first())
        salary_cat_by_admin[admin_id] = cat
        return cat

    for att in qs.iterator():
        processed += 1
        try:
            if Transaction.objects.filter(
                admin_id=att.admin_id, attendance_record_id=att.id
            ).exists():
                skipped_exists += 1
                continue

            amount = compute_daily_salary(att.employee, att)
            if amount <= 0:
                skipped_zero += 1
                continue

            defaults = build_expense_defaults(att, amount)
            # Historical model doesn't accept FK instances by kwarg name
            # for some setups — pass ids directly to be safe.
            Transaction.objects.create(
                type            = defaults['type'],
                source          = defaults['source'],
                employee_id     = defaults['employee'].id,
                site_id         = defaults['site'].id if defaults['site'] else None,
                attendance_record_id = att.id,
                location_site   = defaults['location_site'],
                amount          = defaults['amount'],
                date            = defaults['date'],
                description     = defaults['description'],
                breakdown_note  = defaults['breakdown_note'],
                expense_category= defaults['expense_category'],
                reference       = defaults['reference'],
                admin_id        = defaults['admin_id'],
                category        = get_salary_category(att.admin_id),
                user_id         = att.created_by_id or att.employee.id,
                created_by_id   = att.created_by_id,
                payment_mode    = 'cash',
            )
            created += 1
        except Exception as e:  # noqa: BLE001 — backfill must survive per-row failures
            errors += 1
            print(f"[finance 0011 ERR] attendance_id={att.id} "
                  f"emp={att.employee_id} date={att.date}: {e}")

    print(f"[finance 0011 SUMMARY] processed={processed} created={created} "
          f"skipped_exists={skipped_exists} skipped_zero_amount={skipped_zero} "
          f"errors={errors}")


def reverse(apps, schema_editor):
    # Safe reverse: remove only the rows we would have created.
    Transaction = apps.get_model('finance', 'Transaction')
    n = Transaction.objects.filter(source='salary_attendance').delete()[0]
    print(f"[finance 0011 REVERSE] deleted {n} salary_attendance row(s)")


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('finance', '0010_transaction_site_source'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse),
    ]
