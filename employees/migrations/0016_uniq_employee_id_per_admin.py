"""
Add a DB-level UNIQUE constraint on (admin_id, employee_id) for Employee.

Root cause this closes: SPIM020 had two Employee rows under admin ADM28DCC0
(pk=232 PRAVIN R, pk=237 KARTHIKEYAN). AttendanceRecord writes split across
those pks because different code paths resolved the same employee_id string
to different Employee.pk values — inflating leave counts and making admin
edits appear to "not stick". The user has cleaned up that specific dupe;
this constraint prevents recurrence.

Blank employee_id is legal (many legacy rows) — the partial UNIQUE constraint
uses `condition=~Q(employee_id='')` so blank IDs don't collide with each other.

Safety: a RunPython check runs BEFORE AddConstraint and raises if any dupes
still exist. On Railway this fails loudly (naming the offending groups)
instead of AddConstraint erroring with a cryptic IntegrityError.
"""
from django.db import migrations, models


def assert_no_employee_id_dupes(apps, schema_editor):
    """Guard: refuse to add the constraint while dupes still exist. Names
    the collisions so cleanup is straightforward before re-running."""
    Employee = apps.get_model('employees', 'Employee')
    dupes = (
        Employee.objects
        .exclude(employee_id='')
        .values('admin_id', 'employee_id')
        .annotate(n=models.Count('id'))
        .filter(n__gt=1)
        .order_by('admin_id', 'employee_id')
    )
    dupe_list = list(dupes)
    if dupe_list:
        detail_lines = []
        for row in dupe_list:
            group_pks = list(
                Employee.objects.filter(
                    admin_id=row['admin_id'],
                    employee_id=row['employee_id'],
                ).values_list('id', 'name')
            )
            detail_lines.append(
                f"  admin_id={row['admin_id']!r} employee_id={row['employee_id']!r} "
                f"count={row['n']} rows={group_pks}"
            )
        raise RuntimeError(
            "Cannot add UNIQUE(admin_id, employee_id): duplicate rows exist.\n"
            "Clean them up first (delete or renumber), then re-run this migration.\n"
            + "\n".join(detail_lines)
        )


def noop_reverse(apps, schema_editor):
    """Reversing the check is a no-op — the AddConstraint reverse handles
    dropping the constraint on its own."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0015_salaryupdate_payslip_force_active_until'),
    ]

    operations = [
        migrations.RunPython(assert_no_employee_id_dupes, noop_reverse),
        migrations.AddConstraint(
            model_name='employee',
            constraint=models.UniqueConstraint(
                fields=['admin_id', 'employee_id'],
                condition=~models.Q(employee_id=''),
                name='uniq_employee_id_per_admin',
            ),
        ),
    ]
