"""
0007 — Loosen StockItem.site back to nullable.

The Stock page's Add Stock Item form no longer collects a site (Site is
optional at item-add time). StockMovement.site stays NOT NULL — every
in/out still requires a resolved projects.Site.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0010_tighten_nullable_fks'),
        ('material_stock', '0006_site_fks_clean'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockitem',
            name='site',
            field=models.ForeignKey(
                to='projects.site',
                on_delete=django.db.models.deletion.PROTECT,
                null=True, blank=True,
                related_name='stock_items',
            ),
        ),
    ]
