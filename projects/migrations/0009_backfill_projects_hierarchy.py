"""
Data migration for the Projects module restructure.

For every tenant (admin_id) present in MachineLocation / WorkLog:
  1. Ensure an "Unassigned" ProjectClient exists.
  2. Seed 3 standard ProjectClients: Suzlon, Nuclear Power Plant Kudankulam,
     Gamesa Wind Turbines. Idempotent — safe to re-run on Railway.
  3. For every distinct non-blank WorkLog.site string in this tenant, create
     a Site row (case-insensitive dedup, first-seen casing kept). All new
     sites start under the "Unassigned" client; the admin reassigns via UI.
  4. For every MachineLocation in this tenant, assign machine.site by
     counting site occurrences across its WorkLogs and picking the most
     common non-blank value. Machines with no history land on
     Unassigned/Unassigned.
  5. Seed WorkDetailSuggestion from every existing WorkStatus row so the new
     autocomplete has something to offer on day one.

Reverse: no-op (data merges cannot be split cleanly). Migration 0010's
NOT NULL alter would break if this ever ran in reverse, but Django
never auto-reverses data-migration side effects here.
"""
from collections import Counter
from django.db import migrations
from django.utils import timezone


SEED_CLIENT_NAMES = (
    'Suzlon',
    'Nuclear Power Plant Kudankulam',
    'Gamesa Wind Turbines',
)
UNASSIGNED = 'Unassigned'


def _get_or_create_client(ProjectClient, admin_id, name):
    """Case-insensitive get_or_create for a per-tenant ProjectClient."""
    row = ProjectClient.objects.filter(admin_id=admin_id, name__iexact=name).first()
    if row:
        return row
    return ProjectClient.objects.create(admin_id=admin_id, name=name, is_active=True)


def _get_or_create_site(Site, admin_id, name, client):
    row = Site.objects.filter(admin_id=admin_id, name__iexact=name).first()
    if row:
        # Attach a client if the row was created without one somehow.
        if row.client_id is None and client is not None:
            row.client = client
            row.save(update_fields=['client', 'updated_at'])
        return row
    return Site.objects.create(
        admin_id=admin_id, name=name, client=client, is_active=True,
    )


def _forwards(apps, schema_editor):
    ProjectClient        = apps.get_model('projects', 'ProjectClient')
    Site                 = apps.get_model('projects', 'Site')
    MachineLocation      = apps.get_model('projects', 'MachineLocation')
    WorkLog              = apps.get_model('projects', 'WorkLog')
    WorkStatus           = apps.get_model('projects', 'WorkStatus')
    WorkDetailSuggestion = apps.get_model('projects', 'WorkDetailSuggestion')

    admin_ids = set(
        MachineLocation.objects.values_list('admin_id', flat=True).distinct()
    ) | set(
        WorkLog.objects.values_list('admin_id', flat=True).distinct()
    ) | set(
        WorkStatus.objects.values_list('admin_id', flat=True).distinct()
    )
    admin_ids.discard(None)
    admin_ids.discard('')

    now = timezone.now()
    total_clients = total_sites = total_machines = total_suggestions = 0

    for admin_id in sorted(admin_ids):
        # 1. Unassigned client.
        unassigned_client = _get_or_create_client(ProjectClient, admin_id, UNASSIGNED)

        # 2. Seed the 3 standard clients (idempotent).
        for cname in SEED_CLIENT_NAMES:
            _get_or_create_client(ProjectClient, admin_id, cname)
            total_clients += 1

        # 3. Sites from distinct WorkLog.site strings.
        distinct_sites = (
            WorkLog.objects
            .filter(admin_id=admin_id)
            .exclude(site__isnull=True).exclude(site__exact='')
            .values_list('site', flat=True).distinct()
        )
        seen_lower = set()
        for raw in distinct_sites:
            name = (raw or '').strip()
            if not name:
                continue
            low = name.lower()
            if low in seen_lower:
                continue
            seen_lower.add(low)
            _get_or_create_site(Site, admin_id, name, unassigned_client)
            total_sites += 1

        # Ensure an Unassigned Site under Unassigned client — parking spot.
        unassigned_site = _get_or_create_site(Site, admin_id, UNASSIGNED, unassigned_client)

        # 4. Assign every machine.site.
        machines = MachineLocation.objects.filter(admin_id=admin_id)
        for m in machines:
            if m.site_id:
                continue
            counter = Counter()
            for site_str in WorkLog.objects.filter(
                admin_id=admin_id, location=m,
            ).values_list('site', flat=True):
                s = (site_str or '').strip()
                if s:
                    counter[s.lower()] += 1
            if counter:
                # Winner: most-common (case-insensitive), tie broken by name.
                winner_low, _ = counter.most_common(1)[0]
                site_row = Site.objects.filter(
                    admin_id=admin_id, name__iexact=winner_low,
                ).first()
                m.site = site_row or unassigned_site
            else:
                m.site = unassigned_site
            m.save(update_fields=['site'])
            total_machines += 1

        # 5. Seed WorkDetailSuggestion from existing WorkStatus.
        for ws in WorkStatus.objects.filter(admin_id=admin_id):
            text = (ws.name or '').strip()
            if not text:
                continue
            existing = WorkDetailSuggestion.objects.filter(
                admin_id=admin_id, text__iexact=text,
            ).first()
            if existing:
                continue
            WorkDetailSuggestion.objects.create(
                admin_id=admin_id,
                text=text,
                usage_count=1,
                last_used_at=now,
            )
            total_suggestions += 1

    print(
        f"  [projects.0009] backfill complete — "
        f"clients seeded: {total_clients}, sites: {total_sites}, "
        f"machines assigned: {total_machines}, suggestions: {total_suggestions}"
    )


def _noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0008_projectclient_site_workdetailsuggestion'),
    ]

    operations = [
        migrations.RunPython(_forwards, _noop_reverse),
    ]
