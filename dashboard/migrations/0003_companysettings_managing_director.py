from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_companysettings_admin_id_companysettings_modified_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysettings',
            name='managing_director',
            field=models.CharField(blank=True, default='', max_length=150),
            preserve_default=False,
        ),
    ]
