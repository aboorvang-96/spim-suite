import re

from django.db import migrations

# Indian vehicle registration number, anchored at the start of the name.
#   ^[A-Z]{2}   state code            (TN, KA, ...)
#   [- ]?\d{1,2} RTO district code    (72, 11, ...)
#   [- ]?[A-Z]{0,3} series letters    (BV, DU, K, or none)
#   [- ]?\d{1,4} unique number        (9477, 6644, ...)
# Case-sensitive + .match() => must appear at the very start of `name`, so a
# combined label like "TN72BV9477 (Tata Ace- Venkatesh)" still matches (the
# regno leads), while ordinary person names never do.
VEHICLE_REGNO_RE = re.compile(r'^[A-Z]{2}[- ]?\d{1,2}[- ]?[A-Z]{0,3}[- ]?\d{1,4}')


def backfill_vehicle_flag(apps, schema_editor):
    """
    Set is_vehicle=True for every Employee whose `name` matches the Indian
    vehicle-registration regex. Idempotent — re-running only re-sets the same
    rows True and never unsets a row. All tenants are covered; the flag is a
    per-row attribute, so no cross-tenant data is mixed.

    Prints the count + full list of matched names to stdout so the result is
    visible in Railway deploy logs for post-deploy verification.
    """
    Employee = apps.get_model('employees', 'Employee')

    matched = []
    for emp in Employee.objects.all().order_by('admin_id', 'name'):
        if VEHICLE_REGNO_RE.match((emp.name or '').strip()):
            matched.append(emp)

    # Only write rows that aren't already flagged (keeps it idempotent and
    # avoids needless UPDATEs on re-run).
    to_update = [e for e in matched if not e.is_vehicle]
    for emp in to_update:
        emp.is_vehicle = True
    if to_update:
        Employee.objects.bulk_update(to_update, ['is_vehicle'])

    # ---- Verification log (visible in deploy output) ----------------------
    print('')
    print('[0014_backfill_vehicle_flag] Vehicle backfill summary')
    print('  matched by regex : %d' % len(matched))
    print('  newly flagged    : %d' % len(to_update))
    print('  already flagged  : %d' % (len(matched) - len(to_update)))
    if matched:
        print('  matched names (admin_id | employee_id | name):')
        for emp in matched:
            print('    %-10s | %-12s | %s' % (
                emp.admin_id or '',
                emp.employee_id or '',
                emp.name or '',
            ))
    else:
        print('  (no names matched the vehicle-registration pattern)')
    print('')


def noop_reverse(apps, schema_editor):
    """Reverse is a deliberate no-op: never unset is_vehicle on rollback."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0013_employee_is_vehicle'),
    ]

    operations = [
        migrations.RunPython(backfill_vehicle_flag, noop_reverse),
    ]
