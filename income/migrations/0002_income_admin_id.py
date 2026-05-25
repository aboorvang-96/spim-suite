"""
Migration: add admin_id to Income for consistent tenant scoping.

Schema operation: AddField with default='PENDING'.
Data operation: backfill admin_id from income.user.admin_id.
  - If user.admin_id is set (non-null, non-empty) → use it.
  - Otherwise → fall back to 'USER_<user_pk>' (matches get_admin_id() logic).

Existing queries that scope income by `user` continue to work unchanged.
"""
from django.db import migrations, models


def backfill_income_admin_id(apps, schema_editor):
    Income = apps.get_model('income', 'Income')
    User   = apps.get_model('accounts', 'User')

    # Build mapping: user_pk → effective admin_id (matches get_admin_id() logic)
    user_map = {
        u['pk']: (u['admin_id'] or f"USER_{u['pk']}")
        for u in User.objects.values('pk', 'admin_id')
    }

    for income in Income.objects.all().iterator():
        effective = user_map.get(income.user_id, f'USER_{income.user_id}')
        Income.objects.filter(pk=income.pk).update(admin_id=effective)


def reverse_backfill(apps, schema_editor):
    """Reset to the field default so the schema removal can proceed cleanly."""
    apps.get_model('income', 'Income').objects.update(admin_id='PENDING')


class Migration(migrations.Migration):

    dependencies = [
        ('income', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='income',
            name='admin_id',
            field=models.CharField(db_index=True, default='PENDING', max_length=20),
        ),
        migrations.RunPython(backfill_income_admin_id, reverse_code=reverse_backfill),
    ]
