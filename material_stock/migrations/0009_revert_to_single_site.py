"""
0009 — Revert StockMovement to a single `site` field.

Undoes 0008's source_site + destination_site split. The user decided a
single site column matches the workflow better. Data preserved: the old
`source_site` column is renamed back to `site`; the new `destination_site`
column is dropped.

Uses `atomic = False` — same precedent as 0006 / 0008 (mixed
Remove/Rename/Alter on the same table has hit pending-trigger-event
errors on Postgres in this app before).
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('projects', '0010_tighten_nullable_fks'),
        ('material_stock', '0008_source_destination_sites'),
    ]

    operations = [
        # 1) Drop the destination_site column (no data preservation — this
        # field only shipped in 0008 and was never populated in production).
        migrations.RemoveField(
            model_name='stockmovement',
            name='destination_site',
        ),
        # 2) Rename source_site → site.
        migrations.RenameField(
            model_name='stockmovement',
            old_name='source_site',
            new_name='site',
        ),
        # 3) Restore the plain related_name and on_delete=SET_NULL that
        # matches the new model definition.
        migrations.AlterField(
            model_name='stockmovement',
            name='site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
                related_name='stock_movements',
            ),
        ),
        # 4) Rebuild the composite index under its original name.
        migrations.RemoveIndex(
            model_name='stockmovement',
            name='ms_mv_admin_src_date_idx',
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(
                fields=['admin_id', 'site', 'movement_date'],
                name='ms_mv_admin_site_date_idx',
            ),
        ),
    ]
