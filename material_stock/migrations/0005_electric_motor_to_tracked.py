"""
0005 — Convert "Electric Motor" from a catalog-only brand into a normal
serial-tracked brand, and migrate its ElectricMotorCatalog rows into real
StockItem rows.

What it does, per tenant (admin_id) that owns an "Electric Motor" brand
and/or ElectricMotorCatalog rows:

  1. Ensure an "Electric Motor" Brand exists; force it to
     section='machineries', category='tracked'.
  2. get_or_create a default MaterialType "Electric Motor"
     (tracking_mode='individual').
  3. For every ElectricMotorCatalog row, get_or_create a StockItem keyed on
     the deterministic serial "EM-<original catalog id>":
        purchase_date = row.created_at.date()  (best available date)
        remarks       = "Type: <t>, Brand: <b>, Material: <m>. <remarks>"
        status        = 'available'; holder/site = null; batch/mfg = null
        created_by    = None  (ElectricMotorCatalog has no created_by column)
  4. Delete the migrated catalog rows — the ms_electric_motor_catalog TABLE is
     preserved (kept for archival), only its rows are emptied.

Idempotency:
  * Brand/MaterialType via get-or-create.
  * StockItem via get_or_create on the deterministic (admin_id, material_type,
    serial_no) key — re-running never duplicates.
  * Catalog rows are deleted after migration, so a second run finds zero rows
    and is a clean no-op.  A tenant with zero catalog rows is also a no-op.

Reverse is a deliberate no-op: we never un-migrate tracked stock.
"""
from django.db import migrations
from django.utils import timezone


ELECTRIC_MOTOR = 'Electric Motor'
SKIP_ADMIN_IDS = {'', 'PENDING'}


def _catalog_remarks(row):
    """Fold the flat catalog columns into one readable StockItem.remarks."""
    head = (f"Type: {row.type_name or '—'}, "
            f"Brand: {row.brand or '—'}, "
            f"Material: {row.material or '—'}.")
    tail = (row.remarks or '').strip()
    return f"{head} {tail}".strip()


def forward(apps, schema_editor):
    Brand        = apps.get_model('material_stock', 'Brand')
    MaterialType = apps.get_model('material_stock', 'MaterialType')
    StockItem    = apps.get_model('material_stock', 'StockItem')
    Catalog      = apps.get_model('material_stock', 'ElectricMotorCatalog')

    # Every admin_id that owns an Electric Motor brand OR has catalog rows.
    admin_ids = set()
    for aid in (Brand.objects.filter(name__iexact=ELECTRIC_MOTOR)
                .values_list('admin_id', flat=True)):
        if aid and aid not in SKIP_ADMIN_IDS:
            admin_ids.add(aid)
    for aid in Catalog.objects.values_list('admin_id', flat=True).distinct():
        if aid and aid not in SKIP_ADMIN_IDS:
            admin_ids.add(aid)

    for admin_id in sorted(admin_ids):
        # 1. Ensure + flip the Electric Motor brand.
        brand = (Brand.objects
                 .filter(admin_id=admin_id, name__iexact=ELECTRIC_MOTOR)
                 .first())
        if brand is None:
            brand = Brand.objects.create(
                admin_id=admin_id, name=ELECTRIC_MOTOR,
                category='tracked', section='machineries', is_active=True,
            )
        else:
            brand.section  = 'machineries'
            brand.category = 'tracked'
            brand.is_active = True
            brand.save(update_fields=['section', 'category', 'is_active'])

        # 2. Default material type "Electric Motor" (individual tracking).
        mtype, _ = MaterialType.objects.get_or_create(
            admin_id=admin_id, brand=brand, name=ELECTRIC_MOTOR,
            defaults={'tracking_mode': 'individual', 'is_active': True},
        )

        # 3. Migrate each catalog row → StockItem (deterministic serial key).
        rows = list(Catalog.objects.filter(admin_id=admin_id))
        for row in rows:
            serial = f"EM-{row.id}"
            pdate = (row.created_at.date() if row.created_at
                     else timezone.localdate())
            StockItem.objects.get_or_create(
                admin_id=admin_id, material_type=mtype, serial_no=serial,
                defaults={
                    'purchase_date':       pdate,
                    'batch_no':            None,
                    'mfg_date':            None,
                    'current_holder_name': None,
                    'current_site_name':   None,
                    'status':              'available',
                    'remarks':             _catalog_remarks(row),
                    'created_by':          None,
                },
            )

        # 4. Empty the migrated catalog rows (table structure preserved).
        if rows:
            Catalog.objects.filter(admin_id=admin_id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('material_stock', '0004_brand_section'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
