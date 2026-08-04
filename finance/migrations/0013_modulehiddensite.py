from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finance', '0012_revert_transaction_site_source'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModuleHiddenSite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, max_length=200)),
                ('module', models.CharField(choices=[('expense', 'Expense'), ('income', 'Income')], max_length=20)),
                ('site_name', models.CharField(max_length=200)),
                ('hidden_at', models.DateTimeField(auto_now_add=True)),
                ('hidden_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-hidden_at'],
                'unique_together': {('admin_id', 'module', 'site_name')},
            },
        ),
    ]
