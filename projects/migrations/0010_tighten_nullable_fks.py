"""
Tighten the two FKs introduced by 0008 to NOT NULL, after 0009 has
populated them for every existing row.

If any Site.client_id or MachineLocation.site_id is still NULL when this
migration runs, MySQL will reject the ALTER — deploy fails loudly. That
is intentional: silent NULLs would mean orphans in the tree UI.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0009_backfill_projects_hierarchy'),
    ]

    operations = [
        migrations.AlterField(
            model_name='site',
            name='client',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='sites',
                to='projects.projectclient',
            ),
        ),
        migrations.AlterField(
            model_name='machinelocation',
            name='site',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='machines',
                to='projects.site',
            ),
        ),
    ]
