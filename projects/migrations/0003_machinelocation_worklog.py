from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_project_admin_id_project_created_by_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MachineLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('admin_id', 'name')},
            },
        ),
        migrations.CreateModel(
            name='WorkLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('date', models.DateField()),
                ('site', models.CharField(blank=True, default='', max_length=150)),
                ('work_details', models.TextField(blank=True, default='')),
                ('tmp', models.PositiveIntegerField(default=0, verbose_name='Total Man Power')),
                ('company_name', models.CharField(blank=True, default='', max_length=150)),
                ('remarks', models.CharField(blank=True, default='', max_length=250)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='work_logs_created',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('location', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='work_logs',
                    to='projects.machinelocation',
                )),
            ],
            options={
                'ordering': ['-date', '-created_at'],
            },
        ),
    ]
