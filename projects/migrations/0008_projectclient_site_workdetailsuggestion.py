"""
Schema-only migration for the 2026 Projects module restructure.

Introduces:
  * ProjectClient — Level 1 of the new Work Log tree.
  * Site         — Level 2, nested under ProjectClient.
  * WorkDetailSuggestion — autocomplete corpus for the free-text Work Details.
  * MachineLocation.site — nullable FK to Site (backfilled in 0009, tightened in 0010).

Site.client is created nullable here for backfill safety. Both nullable FKs
(`Site.client`, `MachineLocation.site`) are tightened to NOT NULL by
migration 0010 after 0009 finishes populating them.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0007_worklog_unique_admin_date_location'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectClient',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('name', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('admin_id', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Site',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('name', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='sites',
                    to='projects.projectclient',
                )),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('admin_id', 'name')},
            },
        ),
        migrations.CreateModel(
            name='WorkDetailSuggestion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('text', models.CharField(max_length=200)),
                ('usage_count', models.PositiveIntegerField(default=0)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-usage_count', '-last_used_at'],
                'unique_together': {('admin_id', 'text')},
            },
        ),
        migrations.AddField(
            model_name='machinelocation',
            name='site',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='machines',
                to='projects.site',
            ),
        ),
    ]
