"""
Data migration: merge any pre-existing duplicate WorkLog rows that share
(admin_id, date, location_id).

Why this exists
---------------
The mobile endpoint (`api.views.mobile_worklogs`) previously used a 4-tuple
upsert key `(admin_id, date, location, site)` while the admin endpoint
(`projects.views.work_log_upsert`) used `(admin_id, date, location)`. Two
employees with different Employee.site values punching the same machine on
the same date created two rows for what is logically one entry. The same
admin then tried `update_or_create` on the 3-tuple and got
`MultipleObjectsReturned`.

After this migration, both endpoints share the 3-tuple identity. This
migration cleans up the leftover duplicate rows from the 4-tuple era so the
unified code path doesn't hit `MultipleObjectsReturned` on the very first
call.

Merge strategy (per duplicate group)
------------------------------------
- Canonical row = the oldest pk in the group.
- TMP             = max(tmp) across the group.
- site / work_details / remarks = the latest non-empty value (highest pk).
- employees (M2M) = union of all rows' employees.
- All non-canonical rows are deleted; their M2M relations were already
  copied to the canonical row.

Reversibility: no-op (you can't un-merge once duplicates are gone, but the
schema is untouched so the migration can be reverse-applied without error).
"""
from collections import defaultdict
from django.db import migrations


def _merge_duplicates(apps, schema_editor):
    WorkLog = apps.get_model('projects', 'WorkLog')

    # Group by (admin_id, date, location_id). NULL location_id is a valid
    # bucket — those rows are not duplicates of each other unless date and
    # admin_id also match.
    groups = defaultdict(list)
    for wl in WorkLog.objects.all().order_by('pk'):
        key = (wl.admin_id, wl.date, wl.location_id)
        groups[key].append(wl)

    merged_count = 0
    deleted_count = 0
    for key, rows in groups.items():
        if len(rows) <= 1:
            continue
        canonical = rows[0]
        # Track the best non-empty values across all duplicate rows.
        # Iterate in pk order so the highest-pk (latest) non-empty value wins
        # for fields where last-write-wins is the existing merge semantic.
        max_tmp        = canonical.tmp or 0
        latest_site    = canonical.site or ''
        latest_details = canonical.work_details or ''
        latest_remarks = canonical.remarks or ''

        for dup in rows[1:]:
            if (dup.tmp or 0) > max_tmp:
                max_tmp = dup.tmp or 0
            if (dup.site or '').strip():
                latest_site = dup.site
            if (dup.work_details or '').strip():
                latest_details = dup.work_details
            if (dup.remarks or '').strip():
                latest_remarks = dup.remarks
            # Union employee M2M into canonical row.
            for emp_id in dup.employees.values_list('pk', flat=True):
                canonical.employees.add(emp_id)
            dup.delete()
            deleted_count += 1

        canonical.tmp          = max_tmp
        canonical.site         = latest_site
        canonical.work_details = latest_details
        canonical.remarks      = latest_remarks
        canonical.save(update_fields=[
            'tmp', 'site', 'work_details', 'remarks', 'updated_at',
        ])
        merged_count += 1

    if merged_count or deleted_count:
        print(
            f"  [projects.0005] Merged {merged_count} WorkLog group(s); "
            f"deleted {deleted_count} duplicate row(s)."
        )


def _noop_reverse(apps, schema_editor):
    """Reverse is a no-op — merged rows cannot be split apart again."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0004_workstatus_worklog_employees'),
    ]

    operations = [
        migrations.RunPython(_merge_duplicates, _noop_reverse),
    ]
