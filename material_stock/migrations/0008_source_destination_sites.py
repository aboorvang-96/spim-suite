"""
0008 — Source + Destination sites on StockMovement.

Renames `StockMovement.site` -> `source_site` and adds a new
`destination_site` FK, both nullable. This lets a movement record where
stock is coming FROM and where it's going TO independently, without
forcing either.

Uses `atomic = False` because the migration mixes AlterField + RenameField
+ AddField on the same FK column — Postgres has hit "pending trigger
events" errors in the past on similar mixed DDL in this app (see 0006).
Nothing here is data-migration, just schema, so partial-failure recovery
is a simple re-run.

The `site_name` field on StockMovement was already removed in 0006 — no
change needed here for downloads/history.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('projects', '0010_tighten_nullable_fks'),
        ('material_stock', '0007_stock_item_site_nullable'),
    ]

    operations = [
        # 1) Loosen NOT NULL so the rename doesn't fight existing rows.
        migrations.AlterField(
            model_name='stockmovement',
            name='site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.PROTECT,
                null=True, blank=True,
                related_name='stock_movements',
            ),
        ),
        # 2) Rename site -> source_site (state + column rename).
        migrations.RenameField(
            model_name='stockmovement',
            old_name='site',
            new_name='source_site',
        ),
        # 3) Ensure related_name matches the new field name.
        migrations.AlterField(
            model_name='stockmovement',
            name='source_site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.PROTECT,
                null=True, blank=True,
                related_name='stock_movements_from',
            ),
        ),
        # 4) New destination_site column, nullable.
        migrations.AddField(
            model_name='stockmovement',
            name='destination_site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
                related_name='stock_movements_to',
            ),
        ),
        # 5) Rebuild the composite index that used the old `site` field.
        migrations.RemoveIndex(
            model_name='stockmovement',
            name='ms_mv_admin_site_date_idx',
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(
                fields=['admin_id', 'source_site', 'movement_date'],
                name='ms_mv_admin_src_date_idx',
            ),
        ),
    ]
