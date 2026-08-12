"""Working-site resolution for expense attribution.

The Employee.site field is the employee's PRIMARY/HOME site and must NEVER
be used for expense attribution — an employee based at KKNPP may be deployed
to RADHAPURAM for a cycle, and their salary expense belongs to the site they
actually worked at, not where they nominally live.

Resolution chain (in order):
    1. AttendanceRecord.site_ref.name   — admin-picked Client/Site
    2. AttendanceRecord.working_site    — SPIM Lite mobile per-day field
    3. "OFFICE"                         — fallback bucket

Note the removed rungs:
    - AttendanceRecord.site  → SPIM Lite echo of the employee's home site
    - Employee.site          → the primary/home site
Neither reflects where work was actually done that day.
"""
import logging

logger = logging.getLogger(__name__)

OFFICE_SITE_NAME = 'OFFICE'


def resolve_working_site(attendance):
    """Return the working-site NAME for a single AttendanceRecord.

    Never returns an empty string — falls back to "OFFICE" so every
    attendance row is attributable to some site card.
    """
    ref = getattr(attendance, 'site_ref', None)
    if ref is not None:
        name = (getattr(ref, 'name', '') or '').strip()
        if name:
            return name
    working = (getattr(attendance, 'working_site', '') or '').strip()
    if working:
        return working
    return OFFICE_SITE_NAME


def get_or_create_office_site(admin_id, user=None):
    """Idempotently ensure an "OFFICE" projects.Site exists for the tenant,
    creating the parent ProjectClient if needed. Returns the Site instance.

    Logs the first-time creation per tenant so ops can spot new OFFICE
    buckets appearing in the wild.
    """
    from projects.models import ProjectClient, Site

    client, client_created = ProjectClient.objects.get_or_create(
        admin_id=admin_id,
        name=OFFICE_SITE_NAME,
        defaults={'is_active': True},
    )
    site, site_created = Site.objects.get_or_create(
        admin_id=admin_id,
        name=OFFICE_SITE_NAME,
        defaults={'client': client, 'is_active': True},
    )
    if client_created or site_created:
        logger.info(
            "[OFFICE-SITE] tenant=%s client_created=%s site_created=%s",
            admin_id, client_created, site_created,
        )
    return site
