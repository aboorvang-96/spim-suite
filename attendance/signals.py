"""
Attendance → Expense side-effects.

For every AttendanceRecord saved on or after ATTENDANCE_EXPENSE_CUTOVER
(2026-07-26), upsert a matching finance.Transaction row with
source='salary_attendance'. Attendance is the source of truth for salary
expenses going forward; the legacy monthly SAL-{pk}-YYYY-MM payslip rows
stay for cycles ending before the cut-over.

Delete semantics:
    * status flipped to a non-earning value (absent, no_week_off, etc.) →
      the linked Transaction is removed (amount<=0 short-circuit).
    * AttendanceRecord deleted → CASCADE on Transaction.attendance_record
      removes it. No signal handler needed.

FAILURE POLICY: attendance is the primary write. If anything downstream
here explodes (bad data, DB blip, formula bug), it is caught + logged +
swallowed. Never block the attendance save.
"""
from __future__ import annotations

import logging

from django.db import transaction as db_transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AttendanceRecord

log = logging.getLogger(__name__)


@receiver(post_save, sender=AttendanceRecord)
def sync_expense_from_attendance(sender, instance, created, **kwargs):
    try:
        _apply(instance)
    except Exception:  # noqa: BLE001 — attendance must never fail because of side-effects
        log.exception(
            "sync_expense_from_attendance failed for attendance_id=%s "
            "emp=%s date=%s status=%s",
            instance.id, instance.employee_id, instance.date, instance.status,
        )


def _apply(attendance):
    # Deferred imports — signals module is loaded at app-ready before some
    # of these apps have finished migrating in test setups.
    from employees.salary_calc import (
        compute_daily_salary,
        build_expense_defaults,
        ATTENDANCE_EXPENSE_CUTOVER,
    )
    from finance.models import Transaction, Category

    if attendance.date < ATTENDANCE_EXPENSE_CUTOVER:
        return  # legacy cycle — payslip flow owns this

    amount = compute_daily_salary(attendance.employee, attendance)

    # amount <= 0 → status is non-earning (absent, leave for base_salary
    # employees, etc.). Remove any prior linked expense and stop.
    if amount <= 0:
        with db_transaction.atomic():
            Transaction.objects.filter(
                admin_id=attendance.admin_id,
                attendance_record=attendance,
            ).delete()
        return

    defaults = build_expense_defaults(attendance, amount)
    # Salary Category (tenant-scoped). Created lazily so tenants that
    # haven't touched Finance yet still get the badge / grouping.
    salary_category, _ = Category.objects.get_or_create(
        admin_id=attendance.admin_id,
        name='Salary',
        type='expense',
        defaults={
            'created_by': attendance.created_by,
            'modified_by': attendance.created_by,
        },
    )
    defaults['category'] = salary_category
    # `user` is required (NOT NULL FK on Transaction). Use the person who
    # created the attendance; fall back to the employee's user if any.
    user_for_tx = attendance.created_by
    if user_for_tx is None:
        # No obvious fallback — skip write rather than fail. Attendance
        # rows written before the auth user field was introduced are the
        # only realistic path here.
        log.warning(
            "sync_expense_from_attendance: no created_by on attendance_id=%s"
            " — skipping expense write", attendance.id,
        )
        return

    with db_transaction.atomic():
        Transaction.objects.update_or_create(
            admin_id=attendance.admin_id,
            attendance_record=attendance,
            defaults={
                **defaults,
                'user':       user_for_tx,
                'created_by': user_for_tx,
                'payment_mode': 'cash',
            },
        )
