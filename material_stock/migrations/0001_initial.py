"""
Initial schema for the Material Stock / Inventory backend.

Creates three tenant-scoped tables that back the existing
material_stock/index.html UI (previously localStorage-only):
  - StockSite
  - StockItem
  - StockEntry

Each table has its own `admin_id` for tenant isolation and a `client_id`
that mirrors the frontend's stable JS id so refreshes survive without
losing references.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StockSite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('client_id', models.CharField(db_index=True, max_length=80)),
                ('name', models.CharField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_sites_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Stock Site',
                'verbose_name_plural': 'Stock Sites',
                'ordering': ['name'],
                'unique_together': {('admin_id', 'client_id')},
            },
        ),
        migrations.CreateModel(
            name='StockItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('client_id', models.CharField(db_index=True, max_length=80)),
                ('site_client_id', models.CharField(blank=True, default='', max_length=80)),
                ('item_name', models.CharField(max_length=150)),
                ('brand', models.CharField(blank=True, default='', max_length=150)),
                ('length', models.CharField(blank=True, default='', max_length=50)),
                ('category', models.CharField(blank=True, default='General', max_length=100)),
                ('qty', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('condition', models.CharField(blank=True, default='Good', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_items_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Stock Item',
                'verbose_name_plural': 'Stock Items',
                'ordering': ['item_name', 'brand', 'length'],
                'unique_together': {('admin_id', 'client_id')},
            },
        ),
        migrations.CreateModel(
            name='StockEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('client_id', models.CharField(db_index=True, max_length=80)),
                ('date', models.DateField(blank=True, null=True)),
                ('from_site', models.CharField(blank=True, default='', max_length=200)),
                ('to_site', models.CharField(blank=True, default='', max_length=200)),
                ('item_name', models.CharField(blank=True, default='', max_length=150)),
                ('serial_number', models.CharField(blank=True, default='', max_length=100)),
                ('type_brand', models.CharField(blank=True, default='', max_length=150)),
                ('length', models.CharField(blank=True, default='', max_length=50)),
                ('quantity_out', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('quantity_in', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('remarks', models.TextField(blank=True, default='')),
                ('worker_name', models.CharField(blank=True, default='', max_length=150)),
                ('date_time', models.DateTimeField(blank=True, null=True)),
                ('missing_stock', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('damage_deduction', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('approval_by', models.CharField(blank=True, default='', max_length=150)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_entries_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Stock Entry',
                'verbose_name_plural': 'Stock Entries',
                'ordering': ['-date', '-created_at'],
                'unique_together': {('admin_id', 'client_id')},
            },
        ),
    ]
