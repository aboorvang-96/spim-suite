"""
Attendance → Projects integration.

Keeps the WorkLog side-effect out of `save_attendance` so that view stays a
thin orchestrator and this logic can be exercised in isolation. Every path
here runs inside the caller's `transaction.atomic()` block: any exception
raised from `apply_worklog_sideeffect` rolls back both the WorkLog side
of the write AND the just-saved AttendanceRecord row.

Business rules baked in (per the 2026-07 Attendance/Projects spec):

  * WorkLog is only written for working statuses (`present`, `half_day`).
    Every other status is treated as "did not work" and skips the write.
  * When the attendance row is re-saved with a different machine on the
    same date (or with the machine cleared / status flipped to non-working),
    the employee is removed from the previous WorkLog's M2M. The old
    WorkLog itself is never deleted, even if it becomes empty.
  * A locked WorkLog is respected: the employee is still added to its
    M2M (participation is factual), but no field on the WorkLog is
    touched — Projects module remains the authoritative editor.
  * An unlocked existing WorkLog gets `work_details` filled ONLY if it
    was previously empty. TMP, site, remarks are never overwritten by
    an attendance-side save.
  * New WorkLogs from attendance always start with `tmp=1`.
"""
from projects.models import MachineLocation, WorkLog
from projects.utils import bump_work_detail_suggestion


_WORKING_STATUSES = ('present', 'half_day')


def _remove_from_worklog(admin_id, date, machine_id, employee):
    """Best-effort M2M removal — silently no-ops if the row doesn't exist."""
    if not machine_id:
        return
    wl = WorkLog.objects.filter(
        admin_id=admin_id, date=date, location_id=machine_id,
    ).only('id').first()
    if wl:
        wl.employees.remove(employee)


def apply_worklog_sideeffect(record, prev_machine_id, user):
    """
    Sync the projects.WorkLog side of an attendance write.

    :param record:           the just-saved AttendanceRecord instance.
    :param prev_machine_id:  the record's machine_id BEFORE this save
                             (may be None). Used to detach the employee
                             from any WorkLog they were previously on if
                             the machine changed or was cleared.
    :param user:             request.user, stored as WorkLog.created_by
                             for newly created rows.

    Raises on database error → caller's atomic block rolls back the
    attendance row too. Suggestion bump is best-effort and never raises.
    """
    admin_id = record.admin_id
    new_machine_id = record.machine_id
    is_working = record.status in _WORKING_STATUSES

    # 1. Detach from old WorkLog if the machine changed OR the status
    #    is no longer a working one. When the machine is unchanged and
    #    the status is still working, the same M2M row survives via the
    #    `.add()` below (idempotent).
    if prev_machine_id and (
        prev_machine_id != new_machine_id or not is_working
    ):
        _remove_from_worklog(admin_id, record.date, prev_machine_id, record.employee)

    # 2. Non-working status → nothing more to do. Employee is out of any
    #    WorkLog they may have been on.
    if not is_working:
        return

    # 3. Need both machine AND non-empty work_details to write a WorkLog.
    #    Machine alone → structured link is preserved on the AttendanceRecord
    #    for future reporting, but no WorkLog is created yet. The client
    #    surfaces a UX hint prompting the admin to fill work details.
    work_details = (record.work_details or '').strip()
    if not new_machine_id or not work_details:
        return

    # 4. Upsert the WorkLog. select_related so machine.site.name resolves
    #    without an extra query.
    machine = (
        MachineLocation.objects
        .select_related('site')
        .filter(pk=new_machine_id, admin_id=admin_id)
        .first()
    )
    if not machine:
        # Cross-tenant / deleted mid-request. Fail loudly — caller rolls back.
        raise ValueError('Machine not found for this tenant.')

    site_name = machine.site.name if machine.site_id else ''

    wl, created = WorkLog.objects.get_or_create(
        admin_id=admin_id,
        date=record.date,
        location=machine,
        defaults={
            'site':         site_name,
            'work_details': work_details,
            'tmp':          1,
            'created_by':   user if getattr(user, 'is_authenticated', False) else None,
        },
    )

    if created:
        wl.employees.add(record.employee)
    else:
        # Existing row. Always mirror the employee into the M2M — participation
        # is factual regardless of lock state.
        wl.employees.add(record.employee)

        if not getattr(wl, 'locked', False):
            # Respect prior work_details written by the Projects admin —
            # only fill when currently empty. Never touch TMP / site / remarks
            # / locked / created_by.
            if not (wl.work_details or '').strip():
                wl.work_details = work_details
                wl.save(update_fields=['work_details', 'updated_at'])

    # 5. Best-effort suggestion bump — swallows exceptions.
    bump_work_detail_suggestion(admin_id, work_details, user)


def cleanup_worklog_on_delete(admin_id, date, machine_id, employee):
    """
    Called from `delete_attendance` after the AttendanceRecord row is gone.

    Removes the employee from the WorkLog matching (admin_id, date, machine).
    The WorkLog itself is preserved even if the M2M becomes empty — deciding
    when to prune stale WorkLog rows is a Projects-module concern.
    """
    _remove_from_worklog(admin_id, date, machine_id, employee)
