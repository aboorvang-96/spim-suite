"""
0003 — Seed default brands + material types per tenant.

Tenant enumeration (per plan):
  1. All distinct `admin_id` from accounts.User where role in
     ('admin', 'super_admin').
  2. PLUS any distinct `admin_id` already present in the legacy
     material_stock tables (LegacyStockSite/Item/Entry) not captured above.
  Sentinel/blank admin_ids ('', 'PENDING') are skipped.

Seed data:
  Petzl (tracked):
      Hand Jammer (individual), RIG (individual), ID (individual),
      Shunt (individual), Giri-Giri (individual),
      Harness (batched), Rope (batched)
  IBS (tracked):
      Harness (batched), Hand Jammer (batched)   # NOTE: batched, unlike Petzl
  Electric Motor (catalog_only):  no material types (uses ElectricMotorCatalog)

Idempotent: uses case-insensitive get-or-create for brands and
(admin_id, brand, name) get_or_create for material types, so re-running is
safe.  Reverse is a no-op — rolling back must never delete tenant data that
may since have acquired stock items.
"""
from django.db import migrations


SEED = {
    'Petzl': {
        'category': 'tracked',
        'types': [
            ('Hand Jammer', 'individual'),
            ('RIG',         'individual'),
            ('ID',          'individual'),
            ('Shunt',       'individual'),
            ('Giri-Giri',   'individual'),
            ('Harness',     'batched'),
            ('Rope',        'batched'),
        ],
    },
    'IBS': {
        'category': 'tracked',
        'types': [
            ('Harness',     'batched'),
            ('Hand Jammer', 'batched'),   # batched here, individual under Petzl
        ],
    },
    'Electric Motor': {
        'category': 'catalog_only',
        'types': [],   # no material types — catalog-only
    },
}

SKIP_ADMIN_IDS = {'', 'PENDING'}


def _tenant_admin_ids(apps):
    ids = set()

    User = apps.get_model('accounts', 'User')
    for aid in (User.objects
                .filter(role__in=('admin', 'super_admin'))
                .values_list('admin_id', flat=True)
                .distinct()):
        if aid and aid not in SKIP_ADMIN_IDS:
            ids.add(aid)

    # Fallback: any admin_id already present in legacy tables.
    for model_name in ('LegacyStockSite', 'LegacyStockItem', 'LegacyStockEntry'):
        Model = apps.get_model('material_stock', model_name)
        for aid in Model.objects.values_list('admin_id', flat=True).distinct():
            if aid and aid not in SKIP_ADMIN_IDS:
                ids.add(aid)

    return sorted(ids)


def seed_forward(apps, schema_editor):
    Brand        = apps.get_model('material_stock', 'Brand')
    MaterialType = apps.get_model('material_stock', 'MaterialType')

    for admin_id in _tenant_admin_ids(apps):
        for brand_name, spec in SEED.items():
            # Case-insensitive get-or-create for the brand (matches the
            # uniq_brand_admin_lower_name constraint).
            brand = (Brand.objects
                     .filter(admin_id=admin_id, name__iexact=brand_name)
                     .first())
            if brand is None:
                brand = Brand.objects.create(
                    admin_id=admin_id,
                    name=brand_name,
                    category=spec['category'],
                    is_active=True,
                )

            for type_name, mode in spec['types']:
                MaterialType.objects.get_or_create(
                    admin_id=admin_id,
                    brand=brand,
                    name=type_name,
                    defaults={'tracking_mode': mode, 'is_active': True},
                )


class Migration(migrations.Migration):

    dependencies = [
        ('material_stock', '0002_new_models'),
    ]

    operations = [
        migrations.RunPython(seed_forward, migrations.RunPython.noop),
    ]
