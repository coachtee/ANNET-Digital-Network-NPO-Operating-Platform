import datetime
import random

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.beneficiaries.models import Beneficiary
from apps.compliance.models import ComplianceRule
from apps.compliance.services import sync_obligations_for_organisation
from apps.core.permissions import ORG_ROLE_ADMIN, ORG_ROLE_PROJECT_MANAGER
from apps.documents.models import Document
from apps.expenses.models import Budget, BudgetLine, Expense
from apps.governance.models import GovernanceOfficial
from apps.grants.models import Grant
from apps.memberships.models import MembershipApplication
from apps.monitoring_evaluation.models import Indicator, IndicatorPeriodValue, Outcome
from apps.networks.models import Network, NetworkStaffRole
from apps.opportunities.models import Opportunity
from apps.organisations.models import Organisation, OrganisationMembership
from apps.policies.models import Policy, PolicyVersion
from apps.programmes.models import Activity, Programme
from apps.projects.models import Project

FICTIONAL_ORGS = [
    dict(legal_name="Siyafunda Community Technology Centre", organisation_type="npo", legal_structure="npc",
         province="GP", municipality="Ekurhuleni", sectors=["Digital Skills", "Youth Development"],
         dsd_registered=True, cipc_registered=True, sars_pbo_approved=True, section18a_approved=True,
         public=True, verified=True),
    dict(legal_name="Karoo Women's Health Trust", organisation_type="npo", legal_structure="trust",
         province="NC", municipality="Sol Plaatje", sectors=["Health", "Women's Rights"],
         dsd_registered=True, cipc_registered=False, sars_pbo_approved=True, section18a_approved=False,
         masters_office_registered=True, public=True, verified=True),
    dict(legal_name="Ubuntu Youth Development Network", organisation_type="network", legal_structure="voluntary_association",
         province="WC", municipality="City of Cape Town", sectors=["Youth Development", "Education"],
         dsd_registered=True, cipc_registered=False, sars_pbo_approved=False, section18a_approved=False,
         public=True, verified=False),
    dict(legal_name="Limpopo Early Childhood Development Trust", organisation_type="npo", legal_structure="trust",
         province="LP", municipality="Polokwane", sectors=["Early Childhood Development"],
         dsd_registered=True, cipc_registered=False, sars_pbo_approved=True, section18a_approved=True,
         masters_office_registered=True, public=True, verified=True),
    dict(legal_name="Eastern Cape Environmental Justice Forum", organisation_type="npo", legal_structure="npc",
         province="EC", municipality="Buffalo City", sectors=["Environment", "Advocacy"],
         dsd_registered=False, cipc_registered=True, sars_pbo_approved=False, section18a_approved=False,
         public=False, verified=False),
]

COMPLIANCE_RULES = [
    dict(authority="DSD", name="Registered NPO Annual Narrative & Financial Report",
         description="Registered NPOs must submit an annual narrative and financial report to the Department of Social Development.",
         applicable_entity_types=[], required_registration_statuses={"dsd_registered": True},
         trigger_type=ComplianceRule.TRIGGER_FINANCIAL_YEAR_RELATIVE, frequency=ComplianceRule.FREQUENCY_ANNUAL,
         deadline_rule={"months_after_fy_end": 9},
         evidence_requirements=["Narrative report", "Annual financial statements", "Submission acknowledgement"],
         responsible_role="compliance_officer",
         official_source="Nonprofit Organisations Act 71 of 1997 (demonstration reference — verify against the current DSD guidance before production use)"),
    dict(authority="CIPC", name="Annual Return (NPC)",
         description="Non-profit companies must file an annual return with CIPC.",
         applicable_entity_types=["npc"], required_registration_statuses={"cipc_registered": True},
         trigger_type=ComplianceRule.TRIGGER_ANNIVERSARY, frequency=ComplianceRule.FREQUENCY_ANNUAL,
         deadline_rule={"days_after_anniversary": 30},
         evidence_requirements=["CIPC annual return confirmation"],
         responsible_role="compliance_officer",
         official_source="Companies Act 71 of 2008 (demonstration reference — verify against current CIPC guidance before production use)"),
    dict(authority="SARS", name="PBO Annual Tax Exempt Return (IT12EI)",
         description="Approved Public Benefit Organisations submit an annual tax-exempt organisation return.",
         applicable_entity_types=[], required_registration_statuses={"sars_pbo_approved": True},
         trigger_type=ComplianceRule.TRIGGER_FINANCIAL_YEAR_RELATIVE, frequency=ComplianceRule.FREQUENCY_ANNUAL,
         deadline_rule={"months_after_fy_end": 12},
         evidence_requirements=["IT12EI return", "Annual financial statements"],
         responsible_role="finance_officer",
         official_source="Income Tax Act 58 of 1962, s30 (demonstration reference — verify against current SARS guidance before production use)"),
    dict(authority="POPIA", name="Annual POPIA Compliance Review",
         description="Review data protection practices, the Information Officer registration and processing records.",
         applicable_entity_types=[], required_registration_statuses={},
         trigger_type=ComplianceRule.TRIGGER_FIXED_DATE, frequency=ComplianceRule.FREQUENCY_ANNUAL,
         deadline_rule={"fixed_month_day": "03-31"},
         evidence_requirements=["Information Officer registration", "PAIA manual", "Data processing register"],
         responsible_role="compliance_officer",
         official_source="Protection of Personal Information Act 4 of 2013 (demonstration reference)"),
    dict(authority="Master's Office", name="Trust Annual Accounting",
         description="Registered trusts must account annually to the Master of the High Court.",
         applicable_entity_types=["trust"], required_registration_statuses={"masters_office_registered": True},
         trigger_type=ComplianceRule.TRIGGER_FINANCIAL_YEAR_RELATIVE, frequency=ComplianceRule.FREQUENCY_ANNUAL,
         deadline_rule={"months_after_fy_end": 6},
         evidence_requirements=["Trust financial statements", "Trustee resolutions"],
         responsible_role="treasurer",
         official_source="Trust Property Control Act 57 of 1988 (demonstration reference)"),
]


def _fake_file(name, content=b"Demo seed data placeholder document."):
    return ContentFile(content, name=name)


class Command(BaseCommand):
    help = "Load clearly-fictional demonstration data (network, organisations, compliance rules, programmes, etc). Refuses to run when ENVIRONMENT=production."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing demo organisations before reseeding.")

    def handle(self, *args, **options):
        if not settings.LOAD_DEMO_DATA_ALLOWED:
            raise CommandError("Refusing to load demo data: ENVIRONMENT=production. This command is for development/staging only.")

        self.stdout.write("Seeding ANNET Digital Network demonstration data...")

        network, _ = Network.objects.get_or_create(
            slug="annet", defaults={"name": "ANNET", "tagline": "Unity. Collaboration. Impact."},
        )

        superuser, created = User.objects.get_or_create(
            email="platform-admin@example.com",
            defaults=dict(first_name="Platform", last_name="Admin", is_staff=True, is_superuser=True,
                          is_platform_admin=True, email_verified=True),
        )
        if created:
            superuser.set_password("DemoPass!2026")
            superuser.save()

        network_admin, created = User.objects.get_or_create(
            email="network-admin@example.com",
            defaults=dict(first_name="Network", last_name="Admin", email_verified=True),
        )
        if created:
            network_admin.set_password("DemoPass!2026")
            network_admin.save()
        NetworkStaffRole.objects.get_or_create(network=network, user=network_admin, defaults={"role": "network_admin"})

        for rule_data in COMPLIANCE_RULES:
            ComplianceRule.objects.get_or_create(
                authority=rule_data["authority"], name=rule_data["name"],
                defaults={**rule_data, "last_verified_at": timezone.now().date(), "active": True},
            )
        self.stdout.write(f"  {len(COMPLIANCE_RULES)} compliance rules ready.")

        for i, org_data in enumerate(FICTIONAL_ORGS):
            org, created = Organisation.objects.get_or_create(
                legal_name=org_data["legal_name"],
                defaults=dict(
                    organisation_type=org_data["organisation_type"], legal_structure=org_data["legal_structure"],
                    province=org_data["province"], municipality=org_data["municipality"],
                    sectors=org_data["sectors"], programme_areas=org_data["sectors"],
                    dsd_registered=org_data.get("dsd_registered"), cipc_registered=org_data.get("cipc_registered"),
                    sars_pbo_approved=org_data.get("sars_pbo_approved"), section18a_approved=org_data.get("section18a_approved"),
                    masters_office_registered=org_data.get("masters_office_registered"),
                    financial_year_end="02-28", founding_date=datetime.date(2015 + i, 3, 1),
                    email=f"info@{org_data['legal_name'].lower().split()[0]}.org.za",
                    is_publicly_listed=org_data["public"],
                    public_verification_status="verified" if org_data["verified"] else "unverified",
                    public_about=f"{org_data['legal_name']} works on {', '.join(org_data['sectors'])} in {org_data['province']}.",
                    onboarding_step=Organisation.ONBOARDING_COMPLETE,
                    onboarding_completed_at=timezone.now(),
                ),
            )
            if not created:
                continue

            org_admin_user, _ = User.objects.get_or_create(
                email=f"admin{i}@example.com",
                defaults=dict(first_name="Org", last_name=f"Admin {i+1}", email_verified=True),
            )
            org_admin_user.set_password("DemoPass!2026")
            org_admin_user.save()
            OrganisationMembership.objects.create(organisation=org, user=org_admin_user, role=ORG_ROLE_ADMIN)

            pm_user, _ = User.objects.get_or_create(
                email=f"pm{i}@example.com", defaults=dict(first_name="Programme", last_name=f"Manager {i+1}", email_verified=True),
            )
            pm_user.set_password("DemoPass!2026")
            pm_user.save()
            OrganisationMembership.objects.create(organisation=org, user=pm_user, role=ORG_ROLE_PROJECT_MANAGER)

            sync_obligations_for_organisation(org)

            GovernanceOfficial.objects.create(
                organisation=org, full_name="Thandiwe Mokoena", position="chairperson",
                term_start=datetime.date(2023, 1, 1),
            )
            GovernanceOfficial.objects.create(
                organisation=org, full_name="Sipho Ndlovu", position="treasurer",
                term_start=datetime.date(2023, 1, 1),
            )

            policy_doc = Document.objects.create(
                organisation=org, title="Finance Policy v1", uploaded_by=org_admin_user, visibility="organisation",
                file=_fake_file("finance_policy_v1.pdf"),
            )
            policy = Policy.objects.create(
                organisation=org, name="Finance Policy", category="finance", owner="Treasurer",
                approval_authority="Board of Directors", status="approved",
                approval_date=datetime.date(2025, 3, 1), next_review_date=datetime.date(2027, 3, 1),
            )
            PolicyVersion.objects.create(policy=policy, version_number=1, document=policy_doc, approved_date=datetime.date(2025, 3, 1))

            grant = Grant.objects.create(
                organisation=org, funder_name="Example Foundation", name=f"{org_data['sectors'][0]} Programme Grant",
                amount=random.choice([250000, 500000, 1200000]), status=Grant.STATUS_ACTIVE,
                funding_start=datetime.date(2025, 4, 1), funding_end=datetime.date(2026, 3, 31),
                responsible_manager=pm_user,
            )

            programme = Programme.objects.create(
                organisation=org, name=f"{org_data['sectors'][0]} Programme", programme_area=org_data["sectors"][0],
                status="active", description=f"Delivering {org_data['sectors'][0].lower()} services in {org_data['province']}.",
            )
            programme.grants.add(grant)

            activity = Activity.objects.create(programme=programme, name="Weekly session", scheduled_date=timezone.now().date(), status="delivered")

            for j in range(3):
                beneficiary = Beneficiary.objects.create(
                    organisation=org, programme=programme, mode=Beneficiary.MODE_ATTENDANCE_PARTICIPANT,
                    first_name=f"Participant", last_name=str(j + 1), consent_recorded=True,
                )
                AttendanceRecord.objects.create(
                    organisation=org, programme=programme, activity=activity, beneficiary=beneficiary,
                    attendance_date=timezone.now().date(), recorded_by=pm_user,
                )
            AttendanceRecord.objects.create(
                organisation=org, programme=programme, activity=activity, headcount=12,
                attendance_date=timezone.now().date(), recorded_by=pm_user,
            )

            outcome = Outcome.objects.create(programme=programme, title="Improved participant skills")
            indicator = Indicator.objects.create(
                programme=programme, outcome=outcome, name="People reached", indicator_type=Indicator.TYPE_COUNT,
                target_value=100, baseline_value=0, auto_from_attendance=True,
            )
            IndicatorPeriodValue.objects.create(
                indicator=indicator, period_start=timezone.now().date() - datetime.timedelta(days=30),
                period_end=timezone.now().date(), actual_value=15, means_of_verification="Attendance records",
            )

            project = Project.objects.create(
                organisation=org, grant=grant, programme=programme, name=f"{org_data['sectors'][0]} Delivery Project",
                manager=pm_user, status="active", budget=grant.amount,
                start_date=grant.funding_start, end_date=grant.funding_end,
            )
            budget = Budget.objects.create(project=project, total_amount=grant.amount)
            line = BudgetLine.objects.create(budget=budget, category="Programme materials", allocated_amount=grant.amount / 4)
            Expense.objects.create(
                organisation=org, project=project, budget_line=line, submitted_by=pm_user,
                amount=1500, description="Workshop materials", status=Expense.STATUS_SUBMITTED,
                receipt=_fake_file("receipt.pdf"),
            )

            if i < 3:
                application, _ = MembershipApplication.objects.get_or_create(
                    organisation=org,
                    defaults=dict(status=MembershipApplication.STATUS_APPROVED, motivation="Seeking to strengthen our network ties.",
                                  submitted_at=timezone.now(), decided_at=timezone.now(), decided_by=network_admin),
                )

        Opportunity.objects.get_or_create(
            network=network, title="Community Development Grant Programme",
            defaults=dict(opportunity_type=Opportunity.TYPE_FUNDING, status=Opportunity.STATUS_PUBLISHED,
                          description="Seed funding for community-led development projects.",
                          opening_date=timezone.now().date(), closing_date=timezone.now().date() + datetime.timedelta(days=60),
                          location="National"),
        )
        Opportunity.objects.get_or_create(
            network=network, title="Governance & Compliance Workshop",
            defaults=dict(opportunity_type=Opportunity.TYPE_TRAINING, status=Opportunity.STATUS_PUBLISHED,
                          description="A one-day workshop on board governance and compliance readiness.",
                          opening_date=timezone.now().date(), closing_date=timezone.now().date() + datetime.timedelta(days=20),
                          location="Johannesburg, GP"),
        )

        self.stdout.write(self.style.SUCCESS(
            "Demo data loaded. Sign in as platform-admin@example.com / network-admin@example.com / admin0@example.com "
            "(and admin1..admin4) with password DemoPass!2026 — see UAT_GUIDE.md."
        ))
