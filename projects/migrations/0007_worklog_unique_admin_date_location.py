"""
Enforce the (admin_id, date, location) uniqueness that both the Daily Work
Log and the Work Summary depend on.

Two ops in one migration:

  1) RunPython — merge any duplicate WorkLog rows sharing
     (admin_id, date, location_id). Migration 0005 did the same merge for
     the historical duplicates that the mobile endpoint's older 4-tuple
     key produced. New duplicates can still appear whenever a caller
     bypasses `update_or_create` (e.g. the orphan `work_log_add` view or
     any race that predates this migration), and the `AlterUniqueTogether`
     below would fail with IntegrityError if any survive.

     Canonical row per group = oldest pk. Merge rule:
       tmp          → max across the group
       site         → latest non-empty (highest pk wins)
       work_details → latest non-empty
       remarks      → latest non-empty
       locked       → True if ANY row is locked (safer default)
       employees    → union of every row's M2M
     Duplicates are then deleted; the canonical row is saved.

  2) AlterUniqueTogether — install the DB constraint. From this point on
     every write path (admin upsert, mobile get_or_create, orphan
     work_log_add, direct SQL) is prevented from producing a second row.

Reverse:
  - AlterUniqueTogether is auto-reversed by Django.
  - The merge step's reverse is a no-op — merged rows cannot be split.
"""
from collections import defaultdict
from django.db import migrations


def _merge_duplicates(apps, schema_editor):
    WorkLog = apps.get_model('projects', 'WorkLog')

    groups = defaultdict(list)
    for wl in WorkLog.objects.all().order_by('pk'):
        groups[(wl.admin_id, wl.date, wl.location_id)].append(wl)

    merged_groups = 0
    deleted_rows = 0
    for _key, rows in groups.items():
        if len(rows) <= 1:
            continue
        canonical      = rows[0]
        max_tmp        = canonical.tmp or 0
        latest_site    = canonical.site or ''
        latest_details = canonical.work_details or ''
        latest_remarks = canonical.remarks or ''
        any_locked     = bool(getattr(canonical, 'locked', False))

        for dup in rows[1:]:
            if (dup.tmp or 0) > max_tmp:
                max_tmp = dup.tmp or 0
            if (dup.site or '').strip():
                latest_site = dup.site
            if (dup.work_details or '').strip():
                latest_details = dup.work_details
            if (dup.remarks or '').strip():
                latest_remarks = dup.remarks
            if getattr(dup, 'locked', False):
                any_locked = True
            for emp_id in dup.employees.values_list('pk', flat=True):
                canonical.employees.add(emp_id)
            dup.delete()
            deleted_rows += 1

        canonical.tmp          = max_tmp
        canonical.site         = latest_site
        canonical.work_details = latest_details
        canonical.remarks      = latest_remarks
        canonical.locked       = any_locked
        canonical.save(update_fields=[
            'tmp', 'site', 'work_details', 'remarks', 'locked', 'updated_at',
        ])
        merged_groups += 1

    if merged_groups or deleted_rows:
        print(
            f"  [projects.0007] Merged {merged_groups} WorkLog group(s); "
            f"deleted {deleted_rows} duplicate row(s) before applying the "
            f"unique_together constraint."
        )


def _noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0006_worklog_locked'),
    ]

    operations = [
        migrations.RunPython(_merge_duplicates, _noop_reverse),
        migrations.AlterUniqueTogether(
            name='worklog',
            unique_together={('admin_id', 'date', 'location')},
        ),
    ]
