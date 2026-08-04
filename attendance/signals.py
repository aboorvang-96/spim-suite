"""
Attendance → Expense auto-flow (marker-idempotent, no schema).

For every AttendanceRecord on or after CUTOVER_DATE we upsert exactly one
finance.Transaction row keyed by a deterministic marker stored in the
`reference` field: "[AUTO-SAL:{attendance_pk}]". Signal-driven so admins
never manually reconcile daily wages against attendance.

Deliberate design choices:
  * No new Transaction fields, no new migrations. The marker in
    `reference` (max_length=100, we use ~18 chars) is the whole
    idempotency contract.
  * Salary math is delegated to employees.views.compute_daily_salary_for_attendance
    which shares its weight table with the monthly Salary Manager helper.
  * Historical rows (date < CUTOVER_DATE) are ignored. No backfill.
  * Any failure logs a warning and swallows — attendance saves must never
    break because of downstream expense bookkeeping.
"""

import datetime
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


logger = logging.getLogger(__name__)

# Cutover date — auto-expense rows are only written for attendance dated
# on/after this day. Bump manually if you redeploy and want a fresh
# cutover window; existing rows are unaffected.
CUTOVER_DATE = datetime.date(2026, 8, 4)


def _marker(attendance_pk):
    return f'[AUTO-SAL:{attendance_pk}]'


def _resolve_site(instance):
    ref = getattr(instance, 'site_ref', None)
    if ref is not None:
        name = getattr(ref, 'name', '') or ''
        if name.strip():
            return name.strip()
    site = (instance.site or '').strip()
    return site


def _resolve_user(instance):
    """Attribute the Transaction to attendance.created_by if present, else
    any admin/super_admin user under the same tenant. Returns None if the
    tenant has no admin users at all."""
    if instance.created_by_id:
        return instance.created_by
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return (
        User.objects
        .filter(admin_id=instance.admin_id, role__in=('admin', 'super_admin'))
        .first()
    )


@receiver(post_save, sender='attendance.AttendanceRecord')
def sync_expense_from_attendance(sender, instance, **kwargs):
    from finance.models import Transaction, Category
    from employees.views import compute_daily_salary_for_attendance

    try:
        if instance.date < CUTOVER_DATE:
            return

        marker = _marker(instance.pk)
        existing_qs = Transaction.objects.filter(
            admin_id=instance.admin_id,
            reference=marker,
        )

        amount = compute_daily_salary_for_attendance(instance)
        site = _resolve_site(instance)

        # Unpaid day (absent/leave/etc.) or no site → delete any prior row.
        if amount <= 0 or not site:
            deleted, _ = existing_qs.delete()
            if amount > 0 and not site:
                logger.warning(
                    "AUTO-SAL: no site resolvable for AttendanceRecord "
                    "pk=%s emp=%s date=%s; skipped (deleted=%d)",
                    instance.pk, instance.employee_id, instance.date, deleted,
                )
            return

        user = _resolve_user(instance)
        if user is None:
            logger.warning(
                "AUTO-SAL: no admin user for tenant admin_id=%s; "
                "skipping AttendanceRecord pk=%s",
                instance.admin_id, instance.pk,
            )
            return

        salary_category, _ = Category.objects.get_or_create(
            admin_id=instance.admin_id,
            name='Salary',
            type='expense',
            defaults={'created_by': user, 'modified_by': user},
        )

        description = (
            f"Auto salary — {instance.employee.name} — {instance.date}"
        )

        fields = {
            'user': user,
            'type': 'expense',
            'category': salary_category,
            'amount': amount,
            'description': description,
            'date': instance.date,
            'location_site': site,
            'admin_id': instance.admin_id,
            'modified_by': user,
        }

        row = existing_qs.first()
        if row is not None:
            for k, v in fields.items():
                setattr(row, k, v)
            row.save()
        else:
            Transaction.objects.create(
                reference=marker,
                created_by=user,
                **fields,
            )
    except Exception as exc:
        logger.warning(
            "AUTO-SAL post_save failed for AttendanceRecord pk=%s: %s",
            getattr(instance, 'pk', None), exc,
        )


@receiver(post_delete, sender='attendance.AttendanceRecord')
def remove_expense_on_attendance_delete(sender, instance, **kwargs):
    from finance.models import Transaction
    try:
        Transaction.objects.filter(
            admin_id=instance.admin_id,
            reference=_marker(instance.pk),
        ).delete()
    except Exception as exc:
        logger.warning(
            "AUTO-SAL post_delete failed for AttendanceRecord pk=%s: %s",
            getattr(instance, 'pk', None), exc,
        )
