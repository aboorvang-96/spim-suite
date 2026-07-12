from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0004_attendancerecord_site_working_site'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancerecord',
            name='remarks',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='remarks_locked',
            field=models.BooleanField(default=False),
        ),
    ]
