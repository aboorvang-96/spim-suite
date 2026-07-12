from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0005_merge_duplicate_worklogs'),
    ]

    operations = [
        migrations.AddField(
            model_name='worklog',
            name='locked',
            field=models.BooleanField(default=False),
        ),
    ]
