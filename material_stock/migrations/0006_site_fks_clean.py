"""
0006 — Clean-slate Site FK rollout for StockItem and StockMovement.

WARNING: deleting all StockItem and StockMovement rows for clean site FK
rollout. This is intentional per user confirmation on 2026-08-03.

Existing rows in these two tables are dummy data. Wiping them lets us:

  * Drop StockMovement.site_name (free-text) with no rename / no legacy column.
  * Add StockItem.site   → FK(projects.Site, PROTECT, NOT NULL)
  * Add StockMovement.site → FK(projects.Site, PROTECT, NOT NULL)
  * Add composite indexes (admin_id, site) and (admin_id, site, movement_date).

StockItem.current_site_name is KEPT — it's read by autocomplete
(sites_suggest, serials_suggest) and rendered on Master Control (column +
edit modal). Dropping it would require reworking those touchpoints too;
out of scope for this migration.

Order of operations:
  1. RunPython: delete all StockMovement rows first (FK to StockItem).
  2. RunPython: delete all StockItem rows.
  3. Schema ops in a safe order — add nullable FKs, then flip to NOT NULL,
     then drop site_name, then add indexes.
"""
from django.db import migrations, models
import django.db.models.deletion


def wipe_stock_movements(apps, schema_editor):
    StockMovement = apps.get_model('material_stock', 'StockMovement')
    n = StockMovement.objects.count()
    StockMovement.objects.all().delete()
    print(f"[0006 WIPE] deleted {n} StockMovement row(s)")


def wipe_stock_items(apps, schema_editor):
    StockItem = apps.get_model('material_stock', 'StockItem')
    n = StockItem.objects.count()
    StockItem.objects.all().delete()
    print(f"[0006 WIPE] deleted {n} StockItem row(s)")


def noop_reverse(apps, schema_editor):
    # Wipes are irreversible; the rest of the migration handles its own reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0010_tighten_nullable_fks'),
        ('material_stock', '0005_electric_motor_to_tracked'),
    ]

    operations = [
        # ── 1 & 2. Wipe dummy rows (movements first — FK to items) ───────
        migrations.RunPython(wipe_stock_movements, noop_reverse),
        migrations.RunPython(wipe_stock_items,     noop_reverse),

        # ── 3. StockItem.site (added nullable, then flipped) ─────────────
        migrations.AddField(
            model_name='stockitem',
            name='site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                related_name='stock_items',
            ),
        ),
        migrations.AlterField(
            model_name='stockitem',
            name='site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='stock_items',
            ),
        ),
        migrations.AddIndex(
            model_name='stockitem',
            index=models.Index(fields=['admin_id', 'site'],
                               name='ms_item_admin_site_idx'),
        ),

        # ── 4. Drop old free-text StockMovement.site_name ────────────────
        migrations.RemoveField(
            model_name='stockmovement',
            name='site_name',
        ),

        # ── 5. StockMovement.site (added nullable, then flipped) ─────────
        migrations.AddField(
            model_name='stockmovement',
            name='site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                related_name='stock_movements',
            ),
        ),
        migrations.AlterField(
            model_name='stockmovement',
            name='site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='stock_movements',
            ),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['admin_id', 'site', 'movement_date'],
                               name='ms_mv_admin_site_date_idx'),
        ),
    ]
