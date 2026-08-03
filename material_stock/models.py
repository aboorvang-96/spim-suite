"""
Material Stock / Inventory persistence models.

This module now holds TWO generations of models side by side:

  1. LEGACY (unused UI backend) — the original localStorage-sync tables
     `LegacyStockSite / LegacyStockItem / LegacyStockEntry`.  These were
     renamed from `StockSite / StockItem / StockEntry` purely to free up the
     `StockItem` name for the new design.  Each pins `Meta.db_table` to its
     ORIGINAL table name, so Django emits a state-only `RenameModel` and the
     physical tables + all rows are left completely untouched.  Slated for a
     separate cleanup pass later.

  2. NEW material/stock register — a normalized model per your spec:
        Brand → MaterialType → StockItem (one row per physical unit)
        StockMovement (in/out ledger)
        ElectricMotorCatalog (catalog-only brand, no stock tracking)

     Every new table gets an explicit `db_table` (`ms_*`) so it never
     collides with a legacy `material_stock_*` table.

All models are tenant-isolated by `admin_id` (CharField + db_index), matching
the rest of the project.
"""
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from accounts.date_utils import validate_not_future


# ===========================================================================
# LEGACY MODELS  (renamed, db_table pinned — data untouched, UI retired)
# ===========================================================================

class LegacyStockSite(models.Model):
    """[LEGACY] Site / location that holds inventory."""
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    client_id  = models.CharField(max_length=80, db_index=True)
    name       = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_sites_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'material_stock_stocksite'   # pin → no table rename
        ordering        = ['name']
        unique_together = (('admin_id', 'client_id'),)
        verbose_name        = 'Legacy Stock Site'
        verbose_name_plural = 'Legacy Stock Sites'

    def __str__(self):
        return self.name


class LegacyStockItem(models.Model):
    """[LEGACY] Master inventory item — current quantity at a site."""
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    client_id  = models.CharField(max_length=80, db_index=True)
    site_client_id = models.CharField(max_length=80, blank=True, default='')
    item_name  = models.CharField(max_length=150)
    brand      = models.CharField(max_length=150, blank=True, default='')
    length     = models.CharField(max_length=50,  blank=True, default='')
    category   = models.CharField(max_length=100, blank=True, default='General')
    qty        = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    condition  = models.CharField(max_length=50,  blank=True, default='Good')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_items_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'material_stock_stockitem'   # pin → no table rename
        ordering        = ['item_name', 'brand', 'length']
        unique_together = (('admin_id', 'client_id'),)
        verbose_name        = 'Legacy Stock Item'
        verbose_name_plural = 'Legacy Stock Items'

    def __str__(self):
        return f"{self.item_name} ({self.brand or '-'})"


class LegacyStockEntry(models.Model):
    """[LEGACY] Daily transactional movement: in / out, transfers, adjustments."""
    admin_id        = models.CharField(max_length=20, db_index=True, default='PENDING')
    client_id       = models.CharField(max_length=80, db_index=True)
    date            = models.DateField(null=True, blank=True)
    from_site       = models.CharField(max_length=200, blank=True, default='')
    to_site         = models.CharField(max_length=200, blank=True, default='')
    item_name       = models.CharField(max_length=150, blank=True, default='')
    serial_number   = models.CharField(max_length=100, blank=True, default='')
    type_brand      = models.CharField(max_length=150, blank=True, default='')
    length          = models.CharField(max_length=50,  blank=True, default='')
    quantity_out    = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quantity_in     = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    remarks         = models.TextField(blank=True, default='')
    worker_name     = models.CharField(max_length=150, blank=True, default='')
    date_time       = models.DateTimeField(null=True, blank=True)
    missing_stock   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    damage_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    approval_by     = models.CharField(max_length=150, blank=True, default='')
    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_entries_created',
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'material_stock_stockentry'  # pin → no table rename
        ordering        = ['-date', '-created_at']
        unique_together = (('admin_id', 'client_id'),)
        verbose_name        = 'Legacy Stock Entry'
        verbose_name_plural = 'Legacy Stock Entries'

    def __str__(self):
        return f"{self.date} – {self.item_name} ({self.quantity_in or 0} in / {self.quantity_out or 0} out)"


# ===========================================================================
# NEW MATERIAL / STOCK REGISTER
# ===========================================================================

class Brand(models.Model):
    """A material brand.  `tracked` brands own serial-numbered stock;
    `catalog_only` brands (e.g. Electric Motor) are a reference list with no
    stock tracking (they use ElectricMotorCatalog instead)."""
    TRACKED      = 'tracked'
    CATALOG_ONLY = 'catalog_only'
    CATEGORY_CHOICES = [
        (TRACKED,      'Tracked'),
        (CATALOG_ONLY, 'Catalog only'),
    ]

    # Top-level Master Control section this brand belongs to.  Purely an
    # organisational grouping in the UI — everything about how a brand works
    # (tracked/catalog, material types, items, movements) is identical across
    # sections.  ("Brand" stays the model/table name; the UI labels it
    # "Equipment".)
    EQUIPMENT   = 'equipment'
    MACHINERIES = 'machineries'
    SECTION_CHOICES = [
        (EQUIPMENT,   'Equipment'),
        (MACHINERIES, 'Machineries/Tools'),
    ]

    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    name       = models.CharField(max_length=120)
    category   = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=TRACKED)
    section    = models.CharField(max_length=20, choices=SECTION_CHOICES, default=EQUIPMENT)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ms_brand'
        ordering = ['name']
        constraints = [
            # Unique per tenant, case-insensitive.
            models.UniqueConstraint(
                'admin_id', Lower('name'),
                name='uniq_brand_admin_lower_name',
            ),
        ]
        verbose_name        = 'Brand'
        verbose_name_plural = 'Brands'

    def __str__(self):
        return self.name


class MaterialType(models.Model):
    """A kind of material within a brand (e.g. Rig, Harness, Rope).
    `individual` = serial only; `batched` = serial + batch no + mfg date."""
    INDIVIDUAL = 'individual'
    BATCHED    = 'batched'
    TRACKING_CHOICES = [
        (INDIVIDUAL, 'Individual (serial only)'),
        (BATCHED,    'Batched (serial + batch + mfg date)'),
    ]

    admin_id      = models.CharField(max_length=20, db_index=True, default='PENDING')
    brand         = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='material_types')
    name          = models.CharField(max_length=120)
    tracking_mode = models.CharField(max_length=20, choices=TRACKING_CHOICES, default=INDIVIDUAL)
    is_active     = models.BooleanField(default=True)

    class Meta:
        db_table        = 'ms_material_type'
        ordering        = ['name']
        unique_together = (('admin_id', 'brand', 'name'),)
        verbose_name        = 'Material Type'
        verbose_name_plural = 'Material Types'

    def __str__(self):
        return f"{self.brand.name} · {self.name}"

    @property
    def is_batched(self):
        return self.tracking_mode == self.BATCHED


class StockItem(models.Model):
    """One physical unit of a tracked material type."""
    AVAILABLE = 'available'
    ISSUED    = 'issued'
    LOST      = 'lost'
    DAMAGED   = 'damaged'
    STATUS_CHOICES = [
        (AVAILABLE, 'Available'),
        (ISSUED,    'Issued'),
        (LOST,      'Lost'),
        (DAMAGED,   'Damaged'),
    ]

    admin_id      = models.CharField(max_length=20, db_index=True, default='PENDING')
    material_type = models.ForeignKey(MaterialType, on_delete=models.PROTECT, related_name='items')
    # Home site — optional at the Stock page's Add form; enforced only where
    # it matters (StockMovement.site is still NOT NULL).
    site          = models.ForeignKey(
        'projects.Site', on_delete=models.PROTECT,
        null=True, blank=True, related_name='stock_items',
    )
    serial_no     = models.CharField(max_length=120)
    batch_no      = models.CharField(max_length=120, null=True, blank=True)   # batched only
    mfg_date      = models.DateField(null=True, blank=True)                   # batched only
    purchase_date = models.DateField()

    current_holder_name = models.CharField(max_length=150, null=True, blank=True)
    current_site_name   = models.CharField(max_length=200, null=True, blank=True)
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default=AVAILABLE)
    remarks             = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ms_stockitems_created',
    )

    class Meta:
        db_table        = 'ms_stock_item'
        ordering        = ['material_type', 'purchase_date', 'serial_no']
        # Serial unique per tenant + material type.
        unique_together = (('admin_id', 'material_type', 'serial_no'),)
        indexes = [
            models.Index(fields=['admin_id', 'site'], name='ms_item_admin_site_idx'),
        ]
        verbose_name        = 'Stock Item'
        verbose_name_plural = 'Stock Items'

    def __str__(self):
        return f"{self.serial_no} ({self.material_type})"

    def clean(self):
        super().clean()
        validate_not_future(self.purchase_date, "Purchase date")
        validate_not_future(self.mfg_date, "Manufacturing date")

    def save(self, *args, **kwargs):
        validate_not_future(self.purchase_date, "Purchase date")
        validate_not_future(self.mfg_date, "Manufacturing date")
        super().save(*args, **kwargs)


class ElectricMotorCatalog(models.Model):
    """Flat catalog for the Electric Motor brand — no stock tracking."""
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    type_name  = models.CharField(max_length=150)
    brand      = models.CharField(max_length=150)   # free text
    material   = models.CharField(max_length=150)
    remarks    = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ms_electric_motor_catalog'
        ordering = ['type_name', 'brand']
        verbose_name        = 'Electric Motor Catalog Row'
        verbose_name_plural = 'Electric Motor Catalog'

    def __str__(self):
        return f"{self.type_name} / {self.brand}"


class StockMovement(models.Model):
    """A single in/out transfer of a StockItem."""
    admin_id      = models.CharField(max_length=20, db_index=True, default='PENDING')
    stock_item    = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name='movements')
    movement_date = models.DateField()
    site          = models.ForeignKey(
        'projects.Site', on_delete=models.PROTECT, related_name='stock_movements',
    )
    from_person   = models.CharField(max_length=150, null=True, blank=True)  # null if from stock
    to_person     = models.CharField(max_length=150, null=True, blank=True)  # null if returning to stock
    remarks       = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ms_movements_created',
    )

    class Meta:
        db_table = 'ms_stock_movement'
        ordering = ['-movement_date', '-created_at']
        indexes = [
            models.Index(fields=['admin_id', 'site', 'movement_date'],
                         name='ms_mv_admin_site_date_idx'),
        ]
        verbose_name        = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'

    def __str__(self):
        return f"{self.movement_date} · {self.stock_item.serial_no} · {self.from_person or 'STOCK'} → {self.to_person or 'STOCK'}"

    def clean(self):
        super().clean()
        validate_not_future(self.movement_date, "Movement date")

    def save(self, *args, **kwargs):
        validate_not_future(self.movement_date, "Movement date")
        super().save(*args, **kwargs)
