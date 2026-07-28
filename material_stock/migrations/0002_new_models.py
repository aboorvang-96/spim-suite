"""
0002 — Retire the legacy UI backend (state-only rename) and create the new
material/stock register.

PART 1 (legacy):  StockSite/StockItem/StockEntry are renamed to
LegacyStockSite/LegacyStockItem/LegacyStockEntry.  These are wrapped in
`SeparateDatabaseAndState` with EMPTY `database_operations`, so the rename
happens ONLY in Django's migration state — the physical tables
(`material_stock_stocksite`, `material_stock_stockitem`,
`material_stock_stockentry`) and every row in them are left completely
untouched.  The matching `AlterModelTable` state ops pin each renamed model's
`db_table` back to its original name so model state == models.py.

PART 2 (new):  Create Brand, MaterialType, StockItem, ElectricMotorCatalog,
StockMovement — each with an explicit `ms_*` table name so nothing collides
with the legacy `material_stock_*` tables.
"""
from django.conf import settings
from django.db import migrations, models
from django.db.models.functions import Lower
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('material_stock', '0001_initial'),
    ]

    operations = [
        # -------------------------------------------------------------------
        # PART 1 — legacy rename, STATE ONLY (no SQL touches the old tables)
        # -------------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            database_operations=[],   # <-- DB deliberately untouched
            state_operations=[
                migrations.RenameModel('StockSite',  'LegacyStockSite'),
                migrations.RenameModel('StockItem',  'LegacyStockItem'),
                migrations.RenameModel('StockEntry', 'LegacyStockEntry'),
                migrations.AlterModelTable('legacystocksite',  'material_stock_stocksite'),
                migrations.AlterModelTable('legacystockitem',  'material_stock_stockitem'),
                migrations.AlterModelTable('legacystockentry', 'material_stock_stockentry'),
                migrations.AlterModelOptions(
                    name='legacystocksite',
                    options={'ordering': ['name'],
                             'verbose_name': 'Legacy Stock Site',
                             'verbose_name_plural': 'Legacy Stock Sites'},
                ),
                migrations.AlterModelOptions(
                    name='legacystockitem',
                    options={'ordering': ['item_name', 'brand', 'length'],
                             'verbose_name': 'Legacy Stock Item',
                             'verbose_name_plural': 'Legacy Stock Items'},
                ),
                migrations.AlterModelOptions(
                    name='legacystockentry',
                    options={'ordering': ['-date', '-created_at'],
                             'verbose_name': 'Legacy Stock Entry',
                             'verbose_name_plural': 'Legacy Stock Entries'},
                ),
            ],
        ),

        # -------------------------------------------------------------------
        # PART 2 — new register tables
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='Brand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('name', models.CharField(max_length=120)),
                ('category', models.CharField(choices=[('tracked', 'Tracked'), ('catalog_only', 'Catalog only')], default='tracked', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Brand',
                'verbose_name_plural': 'Brands',
                'db_table': 'ms_brand',
                'ordering': ['name'],
            },
        ),
        migrations.AddConstraint(
            model_name='brand',
            constraint=models.UniqueConstraint(models.F('admin_id'), Lower('name'), name='uniq_brand_admin_lower_name'),
        ),
        migrations.CreateModel(
            name='MaterialType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('name', models.CharField(max_length=120)),
                ('tracking_mode', models.CharField(choices=[('individual', 'Individual (serial only)'), ('batched', 'Batched (serial + batch + mfg date)')], default='individual', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='material_types', to='material_stock.brand')),
            ],
            options={
                'verbose_name': 'Material Type',
                'verbose_name_plural': 'Material Types',
                'db_table': 'ms_material_type',
                'ordering': ['name'],
                'unique_together': {('admin_id', 'brand', 'name')},
            },
        ),
        migrations.CreateModel(
            name='StockItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('serial_no', models.CharField(max_length=120)),
                ('batch_no', models.CharField(blank=True, max_length=120, null=True)),
                ('mfg_date', models.DateField(blank=True, null=True)),
                ('purchase_date', models.DateField()),
                ('current_holder_name', models.CharField(blank=True, max_length=150, null=True)),
                ('current_site_name', models.CharField(blank=True, max_length=200, null=True)),
                ('status', models.CharField(choices=[('available', 'Available'), ('issued', 'Issued'), ('lost', 'Lost'), ('damaged', 'Damaged')], default='available', max_length=20)),
                ('remarks', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ms_stockitems_created', to=settings.AUTH_USER_MODEL)),
                ('material_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='items', to='material_stock.materialtype')),
            ],
            options={
                'verbose_name': 'Stock Item',
                'verbose_name_plural': 'Stock Items',
                'db_table': 'ms_stock_item',
                'ordering': ['material_type', 'purchase_date', 'serial_no'],
                'unique_together': {('admin_id', 'material_type', 'serial_no')},
            },
        ),
        migrations.CreateModel(
            name='ElectricMotorCatalog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('type_name', models.CharField(max_length=150)),
                ('brand', models.CharField(max_length=150)),
                ('material', models.CharField(max_length=150)),
                ('remarks', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Electric Motor Catalog Row',
                'verbose_name_plural': 'Electric Motor Catalog',
                'db_table': 'ms_electric_motor_catalog',
                'ordering': ['type_name', 'brand'],
            },
        ),
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('movement_date', models.DateField()),
                ('site_name', models.CharField(max_length=200)),
                ('from_person', models.CharField(blank=True, max_length=150, null=True)),
                ('to_person', models.CharField(blank=True, max_length=150, null=True)),
                ('remarks', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ms_movements_created', to=settings.AUTH_USER_MODEL)),
                ('stock_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='movements', to='material_stock.stockitem')),
            ],
            options={
                'verbose_name': 'Stock Movement',
                'verbose_name_plural': 'Stock Movements',
                'db_table': 'ms_stock_movement',
                'ordering': ['-movement_date', '-created_at'],
            },
        ),
    ]
