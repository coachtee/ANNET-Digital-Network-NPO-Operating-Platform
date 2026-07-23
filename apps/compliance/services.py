"""
Compliance rules engine (spec section 15/17).

``sync_obligations_for_organisation`` evaluates every active
ComplianceRule against an organisation's captured attributes and
creates/updates the corresponding ComplianceObligation instances with a
computed due date. It is safe to call repeatedly (e.g. after every
onboarding step, or from a scheduled command) — it never duplicates an
obligation for the same organisation/rule/due_date, and it does not
touch obligations whose rule no longer applies beyond marking them
Not Applicable.
"""
import calendar
from datetime import date, timedelta

from django.utils import timezone

from apps.compliance.models import ComplianceObligation, ComplianceRule


def _add_months(source_date: date, months: int) -> date:
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _roll_forward_annual(base_month_day_date: date, today: date) -> date:
    """Given a date representing month/day only (year ignored), return the
    next occurrence on/after today."""
    candidate = base_month_day_date.replace(year=today.year)
    if candidate < today:
        candidate = base_month_day_date.replace(year=today.year + 1)
    return candidate


def compute_due_date(rule: ComplianceRule, organisation, today=None) -> date | None:
    today = today or timezone.now().date()
    rule_cfg = rule.deadline_rule or {}

    if rule.trigger_type == ComplianceRule.TRIGGER_FINANCIAL_YEAR_RELATIVE:
        if not organisation.financial_year_end:
            return None
        try:
            month, day = (int(p) for p in organisation.financial_year_end.split("-"))
        except (ValueError, AttributeError):
            return None
        fy_end_this_year = date(today.year, month, min(day, calendar.monthrange(today.year, month)[1]))
        months_after = rule_cfg.get("months_after_fy_end", 0)
        due = _add_months(fy_end_this_year, months_after)
        if due < today:
            fy_end_next_year = date(today.year + 1, month, min(day, calendar.monthrange(today.year + 1, month)[1]))
            due = _add_months(fy_end_next_year, months_after)
        return due

    if rule.trigger_type == ComplianceRule.TRIGGER_FIXED_DATE:
        month_day = rule_cfg.get("fixed_month_day")
        if not month_day:
            return None
        month, day = (int(p) for p in month_day.split("-"))
        base = date(today.year, month, min(day, calendar.monthrange(today.year, month)[1]))
        return _roll_forward_annual(base, today)

    if rule.trigger_type == ComplianceRule.TRIGGER_ANNIVERSARY:
        if not organisation.founding_date:
            return None
        days_after = rule_cfg.get("days_after_anniversary", 0)
        base = organisation.founding_date.replace(year=today.year)
        due = base + timedelta(days=days_after)
        if due < today:
            due = organisation.founding_date.replace(year=today.year + 1) + timedelta(days=days_after)
        return due

    # Event-triggered rules have no computed due date until the event is recorded.
    return None


def sync_obligations_for_organisation(organisation):
    created, updated = 0, 0
    active_rules = ComplianceRule.objects.filter(active=True)

    for rule in active_rules:
        applies = rule.applies_to(organisation)
        existing_open = organisation.compliance_obligations.filter(rule=rule).exclude(
            status__in=[ComplianceObligation.STATUS_SUBMITTED, ComplianceObligation.STATUS_EVIDENCE_RECORDED]
        )

        if not applies:
            n = existing_open.update(status=ComplianceObligation.STATUS_NOT_APPLICABLE)
            updated += n
            continue

        due_date = compute_due_date(rule, organisation)
        obligation, was_created = ComplianceObligation.objects.get_or_create(
            organisation=organisation, rule=rule, due_date=due_date,
            defaults={"status": ComplianceObligation.STATUS_NOT_STARTED},
        )
        if was_created:
            created += 1
        elif obligation.status == ComplianceObligation.STATUS_NOT_APPLICABLE:
            obligation.status = ComplianceObligation.STATUS_NOT_STARTED
            obligation.save(update_fields=["status"])
            updated += 1

        if obligation.is_overdue and obligation.status not in ComplianceObligation.READINESS_STATUSES:
            if obligation.status != ComplianceObligation.STATUS_OVERDUE:
                obligation.status = ComplianceObligation.STATUS_OVERDUE
                obligation.save(update_fields=["status"])

    return {"created": created, "updated": updated}
