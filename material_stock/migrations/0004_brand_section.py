"""
0004 — Add `Brand.section` (schema only).

A top-level Master Control grouping: 'equipment' (default) or 'machineries'.
All existing rows take the default 'equipment'.  Migration 0005 (data) then
moves the "Electric Motor" brand to 'machineries'.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('material_stock', '0003_seed_brands'),
    ]

    operations = [
        migrations.AddField(
            model_name='brand',
            name='section',
            field=models.CharField(
                max_length=20,
                default='equipment',
                choices=[
                    ('equipment',   'Equipment'),
                    ('machineries', 'Machineries/Tools'),
                ],
            ),
        ),
    ]
