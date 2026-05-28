"""
Material Stock / Inventory persistence models.

Scope: minimal backend to back the existing material_stock/index.html UI
that previously stored everything in browser localStorage. No UI changes.
No new business logic. Every row is tenant-isolated by `admin_id` and
optionally tagged with `client_id` — the frontend-generated stable key
so the same JS code paths keep working after a refresh.

Three small tables:

  StockSite   – the master sites list (was localStorage SITES_KEY).
  StockItem   – the master stock list  (was localStorage MASTER_KEY).
  StockEntry  – the daily entries log  (was localStorage STORAGE_KEY).

All three follow the same multi-tenant pattern as the rest of the project
(`admin_id` CharField + db_index). No FK to AUTH_USER_MODEL is set CASCADE —
we use SET_NULL so deleting a user does not wipe tenant inventory.
"""
from django.conf import settings
from django.db import models


class StockSite(models.Model):
    """Site / location that holds inventory."""
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    # Frontend-generated stable key (e.g. "gloc-giga-hq"). Lets the JS keep
    # using its existing site identifiers without round-tripping to a
    # server-issued integer id.
    client_id  = models.CharField(max_length=80, db_index=True)
    name       = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_sites_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering        = ['name']
        unique_together = (('admin_id', 'client_id'),)
        verbose_name        = 'Stock Site'
        verbose_name_plural = 'Stock Sites'

    def __str__(self):
        return self.name


class StockItem(models.Model):
    """Master inventory item — current quantity at a site."""
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    client_id  = models.CharField(max_length=80, db_index=True)
    # The frontend stores siteId on the row; we mirror that as a free-text
    # column rather than FK so the JS keeps using its own ids. Tenant
    # isolation is provided by admin_id; cross-site referential integrity
    # is the frontend's responsibility (same behavior as before).
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
        ordering        = ['item_name', 'brand', 'length']
        unique_together = (('admin_id', 'client_id'),)
        verbose_name        = 'Stock Item'
        verbose_name_plural = 'Stock Items'

    def __str__(self):
        return f"{self.item_name} ({self.brand or '-'})"


class StockEntry(models.Model):
    """Daily transactional movement: in / out, transfers, adjustments."""
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
        ordering        = ['-date', '-created_at']
        unique_together = (('admin_id', 'client_id'),)
        verbose_name        = 'Stock Entry'
        verbose_name_plural = 'Stock Entries'

    def __str__(self):
        return f"{self.date} – {self.item_name} ({self.quantity_in or 0} in / {self.quantity_out or 0} out)"
