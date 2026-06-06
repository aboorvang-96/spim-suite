# Generated manually for Income/Expense restructure.
# Adds three new fields to the Income model:
#   * from_account — Site-detail "From Account" column
#   * to_account   — Site-detail "To Account" column
#   * remarks      — Site-detail "Remarks" column (separate from `description`)
# All three are CharField with blank=True, default='' so existing rows are
# valid without a data migration.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('income', '0004_merge_0002_income_admin_id_0003_alter_income_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='income',
            name='from_account',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='income',
            name='to_account',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='income',
            name='remarks',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
