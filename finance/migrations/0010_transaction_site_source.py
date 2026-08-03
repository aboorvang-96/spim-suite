"""
0010 — Site FK, source, employee FK, attendance_record FK, breakdown_note on
finance.Transaction. Plus a partial unique on (admin_id, attendance_record)
so the attendance→expense signal can't insert duplicates on a race.

Data step (bottom): backfill `source` on every existing row —
  reference startswith 'SAL-' → 'salary_payslip'
  everything else            → 'manual'

`atomic = False` — schema + RunPython in one migration triggers the same
"pending trigger events" Postgres error we hit in material_stock/0006. Split
per-op semantics: each schema op is its own atomic step under the hood, but
the migration file as a whole doesn't wrap them.
"""
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


def backfill_source(apps, schema_editor):
    Transaction = apps.get_model('finance', 'Transaction')
    payslip = Transaction.objects.filter(reference__startswith='SAL-').update(
        source='salary_payslip')
    manual  = Transaction.objects.exclude(reference__startswith='SAL-').update(
        source='manual')
    print(f"[finance 0010 BACKFILL] source='salary_payslip' set on "
          f"{payslip} rows; source='manual' set on {manual} rows")


def noop_reverse(apps, schema_editor):
    # Fields are being dropped by the reverse of the schema ops; nothing to
    # undo at data level.
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('finance',    '0009_transaction_unique_salary_ref'),
        ('projects',   '0010_tighten_nullable_fks'),
        ('employees',  '0015_salaryupdate_payslip_force_active_until'),
        ('attendance', '0008_attendance_client_site'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.PROTECT,
                null=True, blank=True,
                related_name='finance_transactions',
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='source',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('manual',            'Manual'),
                    ('salary_attendance', 'Salary — Attendance'),
                    ('salary_payslip',    'Salary — Payslip'),
                    ('material',          'Material'),
                    ('other',             'Other'),
                ],
                default='manual',
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='employee',
            field=models.ForeignKey(
                to='employees.employee',
                on_delete=django.db.models.deletion.PROTECT,
                null=True, blank=True,
                related_name='transaction_entries',
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='attendance_record',
            field=models.ForeignKey(
                to='attendance.attendancerecord',
                on_delete=django.db.models.deletion.CASCADE,
                null=True, blank=True,
                related_name='transaction_entries',
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='breakdown_note',
            field=models.CharField(max_length=300, blank=True, default=''),
        ),
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(
                fields=['admin_id', 'attendance_record'],
                condition=Q(attendance_record__isnull=False),
                name='unique_tx_per_attendance',
            ),
        ),
        # Data step LAST so all the new columns exist when we write.
        migrations.RunPython(backfill_source, noop_reverse),
    ]
