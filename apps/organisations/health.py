"""
Organisation Health Check scoring engine (spec section 19).

Every dimension score is computed from real records and returns a list of
concrete, human-readable reasons plus recommended actions — "explainable"
per the spec, never a black-box number. This is readiness/self-assessment
information, not a legal or regulatory certification (spec section 1).
"""
from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone


@dataclass
class DimensionScore:
    key: str
    label: str
    score: int
    reasons: list = field(default_factory=list)
    recommended_actions: list = field(default_factory=list)


def _registration_readiness(org):
    reasons, actions = [], []
    fields_checked = [
        ("legal_structure", "Legal structure selected"),
        ("dsd_registered", "DSD registration status captured"),
        ("cipc_registered", "CIPC registration status captured"),
        ("sars_pbo_approved", "SARS PBO status captured"),
        ("section18a_approved", "Section 18A status captured"),
    ]
    answered = 0
    for fname, label in fields_checked:
        value = getattr(org, fname)
        if value not in (None, ""):
            answered += 1
            reasons.append(f"{label}.")
        else:
            actions.append(f"Capture {label.lower()}.")
    score = round((answered / len(fields_checked)) * 100)
    return DimensionScore("registration", "Registration Readiness", score, reasons, actions)


def _compliance_readiness(org):
    obligations = org.compliance_obligations.all()
    total = obligations.count()
    if total == 0:
        return DimensionScore(
            "compliance", "Compliance Readiness", 0,
            ["No compliance obligations have been generated yet."],
            ["Complete your registration status so the Compliance Passport can identify applicable obligations."],
        )
    from apps.compliance.models import ComplianceObligation

    ready = obligations.filter(status__in=ComplianceObligation.READINESS_STATUSES).count()
    overdue = sum(1 for o in obligations if o.is_overdue)
    score = round((ready / total) * 100)
    reasons = [f"{ready} of {total} compliance obligations are submitted, evidenced, or not applicable."]
    actions = []
    if overdue:
        reasons.append(f"{overdue} obligation(s) are overdue.")
        actions.append("Review and action overdue items on your Compliance Calendar.")
    if ready < total:
        actions.append("Work through outstanding items on your Compliance Passport.")
    return DimensionScore("compliance", "Compliance Readiness", score, reasons, actions)


def _governance(org):
    reasons, actions = [], []
    active_officials = org.governance_officials.filter(status="active")
    score = 0
    key_positions = {"chairperson", "treasurer", "secretary"}
    filled_positions = set(active_officials.values_list("position", flat=True)) & key_positions
    score += round((len(filled_positions) / len(key_positions)) * 60)
    if filled_positions:
        reasons.append(f"Key positions filled: {', '.join(sorted(filled_positions))}.")
    missing = key_positions - filled_positions
    if missing:
        actions.append(f"Appoint or record: {', '.join(sorted(missing))}.")

    recent_meeting = org.governance_meetings.filter(
        is_held=True, scheduled_date__gte=timezone.now() - timedelta(days=365)
    ).exists()
    if recent_meeting:
        score += 40
        reasons.append("A governance meeting was held within the last 12 months.")
    else:
        actions.append("Record a board/governance meeting held within the last 12 months.")
    return DimensionScore("governance", "Governance", min(score, 100), reasons, actions)


def _policies(org):
    key_categories = {"governance", "finance", "hr", "popia", "safeguarding"}
    approved = set(
        org.policies.filter(status="approved", category__in=key_categories).values_list("category", flat=True)
    )
    score = round((len(approved) / len(key_categories)) * 100)
    reasons = [f"{len(approved)} of {len(key_categories)} key policy categories have an approved policy."]
    missing = key_categories - approved
    actions = [f"Approve a {cat} policy." for cat in sorted(missing)]
    return DimensionScore("policies", "Policies", score, reasons, actions)


def _programme_management(org):
    programmes = org.programmes.all()
    total = programmes.count()
    if total == 0:
        return DimensionScore(
            "programme_management", "Programme Management", 0,
            ["No programmes have been set up yet."], ["Create your first programme."],
        )
    active = programmes.filter(status="active").count()
    described = programmes.exclude(description="").count()
    score = round(((active / total) * 60) + ((described / total) * 40))
    reasons = [f"{active} of {total} programmes are active.", f"{described} of {total} programmes have a description."]
    actions = [] if described == total else ["Add a description to every programme."]
    return DimensionScore("programme_management", "Programme Management", score, reasons, actions)


def _me(org):
    from apps.monitoring_evaluation.models import Indicator

    indicators = Indicator.objects.filter(programme__organisation=org)
    total = indicators.count()
    if total == 0:
        return DimensionScore(
            "me", "M&E", 0, ["No indicators have been set up yet."],
            ["Define at least one outcome/output indicator per active programme."],
        )
    with_actuals = indicators.filter(period_values__isnull=False).distinct().count()
    score = round((with_actuals / total) * 100)
    reasons = [f"{with_actuals} of {total} indicators have at least one recorded actual value."]
    actions = [] if with_actuals == total else ["Record actual values for indicators that are still outstanding."]
    return DimensionScore("me", "M&E", score, reasons, actions)


def _financial_accountability(org):
    from apps.expenses.models import Expense

    expenses = Expense.objects.filter(organisation=org)
    total = expenses.count()
    if total == 0:
        return DimensionScore(
            "financial_accountability", "Financial Accountability", 0,
            ["No expenses have been recorded yet."],
            ["Set up a project budget and start recording expenses with receipt evidence."],
        )
    reviewed = expenses.exclude(status="submitted").count()
    with_receipt = expenses.exclude(receipt="").count()
    score = round(((reviewed / total) * 50) + ((with_receipt / total) * 50))
    reasons = [
        f"{reviewed} of {total} expenses have been reviewed (approved or rejected).",
        f"{with_receipt} of {total} expenses have receipt evidence attached.",
    ]
    actions = [] if reviewed == total else ["Review outstanding submitted expenses."]
    return DimensionScore("financial_accountability", "Financial Accountability", score, reasons, actions)


DIMENSION_FUNCS = [
    _registration_readiness, _compliance_readiness, _governance,
    _policies, _programme_management, _me, _financial_accountability,
]


def compute_health_check(organisation):
    dimensions = [fn(organisation) for fn in DIMENSION_FUNCS]
    overall = round(sum(d.score for d in dimensions) / len(dimensions))
    return {"overall": overall, "dimensions": dimensions}
