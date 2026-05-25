from django.db import migrations


def populate_location_sites(apps, schema_editor):
    Employee     = apps.get_model('employees', 'Employee')
    Transaction  = apps.get_model('finance', 'Transaction')
    Income       = apps.get_model('income', 'Income')
    LocationSite = apps.get_model('branches', 'LocationSite')

    seen = {}  # admin_id -> set of lowercased names already queued

    def add_loc(admin_id, name):
        name = (name or '').strip()
        if not name:
            return
        bucket = seen.setdefault(admin_id, set())
        if name.lower() not in bucket:
            bucket.add(name.lower())
            if not LocationSite.objects.filter(admin_id=admin_id, name__iexact=name).exists():
                LocationSite.objects.create(admin_id=admin_id, name=name)

    # From Employee records: combine location + site
    for e in Employee.objects.all():
        loc  = (e.location or '').strip()
        site = (e.site or '').strip()
        if loc and site:
            add_loc(e.admin_id, f"{loc} / {site}")
        elif loc:
            add_loc(e.admin_id, loc)
        elif site:
            add_loc(e.admin_id, site)

    # From Transaction (expense/income) records
    for t in Transaction.objects.exclude(location_site__isnull=True).exclude(location_site=''):
        add_loc(t.admin_id, t.location_site)

    # From Income records (admin_id lives on the user)
    for i in Income.objects.exclude(location_site='').select_related('user'):
        if i.user:
            admin_id = getattr(i.user, 'admin_id', 'PENDING')
            add_loc(admin_id, i.location_site)


class Migration(migrations.Migration):

    dependencies = [
        ('branches', '0003_locationsite'),
        ('employees', '0001_initial'),
        # Bumped: this RunPython references Transaction.location_site (added in
        # finance.0006) and Income.location_site (added in income.0002_*).
        # Earlier dependency versions caused FieldError on a clean migrate.
        ('finance',   '0006_transaction_location_site_transaction_payment_by_and_more'),
        ('income',    '0002_income_income_type_income_location_site_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_location_sites, migrations.RunPython.noop),
    ]
