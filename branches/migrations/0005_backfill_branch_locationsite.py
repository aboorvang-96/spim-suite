from django.db import migrations


def backfill_branches(apps, schema_editor):
    """Register the combined 'Name / Location' entry for every existing branch."""
    Branch       = apps.get_model('branches', 'Branch')
    LocationSite = apps.get_model('branches', 'LocationSite')

    for b in Branch.objects.all():
        name = (b.name or '').strip()
        loc  = (b.location or '').strip()

        if name and loc:
            combined = f"{name} / {loc}"
        elif name:
            combined = name
        elif loc:
            combined = loc
        else:
            continue

        if not LocationSite.objects.filter(admin_id=b.admin_id, name__iexact=combined).exists():
            LocationSite.objects.create(admin_id=b.admin_id, name=combined)


class Migration(migrations.Migration):

    dependencies = [
        ('branches', '0004_populate_locationsite'),
    ]

    operations = [
        migrations.RunPython(backfill_branches, migrations.RunPython.noop),
    ]
