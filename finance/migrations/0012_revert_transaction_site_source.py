"""
0012 — Revert 0010 + 0011.

The Income/Expense restructure landed on the wrong app (finance/) — the
real Expenses page lives elsewhere. This migration undoes the schema
changes 0010 introduced and deletes the ~203 salary_attendance rows 0011
backfilled. Historical salary_payslip rows are LEFT UNTOUCHED — their
`source` value goes away with the column, but the underlying Transaction
rows (with their SAL-* references) stay put.

Order:
    1. Delete every Transaction where source='salary_attendance'.
    2. Drop the partial unique constraint unique_tx_per_attendance.
    3. Drop the five fields added in 0010:
       site, source, employee, attendance_record, breakdown_note.

`atomic = False` — schema + RunPython in one migration triggers the same
"pending trigger events" Postgres error we hit in material_stock/0006.
"""
from django.db import migrations, models
from django.db.models import Q


def delete_salary_attendance_rows(apps, schema_editor):
    Transaction = apps.get_model('finance', 'Transaction')
    n, _ = Transaction.objects.filter(source='salary_attendance').delete()
    print(f"[finance 0012 REVERT] deleted {n} salary_attendance row(s)")


def noop_reverse(apps, schema_editor):
    # Rolling forward past this revert requires re-applying 0010/0011 —
    # not something this migration can do on its own.
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('finance', '0011_backfill_attendance_expenses'),
    ]

    operations = [
        # 1. Data purge — must happen before the columns are dropped
        #    because we filter on `source`.
        migrations.RunPython(delete_salary_attendance_rows, noop_reverse),

        # 2. Drop the partial unique constraint that references
        #    attendance_record — has to go before the column is removed.
        migrations.RemoveConstraint(
            model_name='transaction',
            name='unique_tx_per_attendance',
        ),

        # 3. Drop the five fields 0010 added. Order among these doesn't
        #    matter, but keep it stable so the schema history reads
        #    cleanly.
        migrations.RemoveField(model_name='transaction', name='attendance_record'),
        migrations.RemoveField(model_name='transaction', name='employee'),
        migrations.RemoveField(model_name='transaction', name='site'),
        migrations.RemoveField(model_name='transaction', name='source'),
        migrations.RemoveField(model_name='transaction', name='breakdown_note'),

        # 4. Log the outcome so it's visible in Railway deploy output.
        migrations.RunPython(
            lambda apps, se: print("[finance 0012 REVERT] dropped 5 fields."),
            noop_reverse,
        ),
    ]
