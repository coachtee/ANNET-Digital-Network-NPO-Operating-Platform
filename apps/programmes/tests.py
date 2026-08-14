from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import ORG_ROLE_ADMIN
from apps.documents.models import Document
from apps.expenses.models import Budget, BudgetLine
from apps.monitoring_evaluation.models import Indicator, IndicatorPeriodValue, Outcome, Output
from apps.organisations.models import Organisation, OrganisationMembership
from apps.programmes.models import Activity, Programme
from apps.programmes.services import (
    compute_programme_attention,
    compute_programme_progress,
    compute_programme_readiness,
    programme_budget_summary,
)
from apps.projects.forms import ProjectForm
from apps.projects.models import Project
from apps.projects.services import project_finance_summary

PASSWORD = "TestPass!2026"


class ProgrammeCreationTests(TestCase):
    """The Programme Wizard is gone. "New Programme" is a short create
    form (name/area/status/start/end); everything else is filled in
    progressively inside the Programme Workspace afterwards -- see
    ProgrammeWorkspaceOverviewTests, ProgrammeReadinessTests and the
    DOPA demonstration scenario for that progressive flow."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)

    def test_create_programme_lands_straight_in_the_workspace(self):
        resp = self.client.post(reverse("programmes:list", kwargs={"slug": self.organisation.slug}), {
            "name": "Youth Digital Literacy Initiative", "programme_area": "education_skills",
            "status": Programme.STATUS_PLANNED, "start_date": "2026-04-01", "end_date": "2027-03-31",
        })
        programme = Programme.objects.get(organisation=self.organisation)
        self.assertEqual(programme.name, "Youth Digital Literacy Initiative")
        self.assertRedirects(resp, reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": programme.id}))

    def test_new_programme_never_carries_data_from_another_programme(self):
        # Regression test for the original bug: creating a new Programme
        # must never resume or inherit data from another, unrelated one.
        other = Programme.objects.create(
            organisation=self.organisation, name="Existing Programme",
            description="Should never leak into a new programme", need_and_background="Old need",
        )
        resp = self.client.post(reverse("programmes:list", kwargs={"slug": self.organisation.slug}), {
            "name": "Brand New Programme", "status": Programme.STATUS_PLANNED,
        })
        new_programme = Programme.objects.exclude(id=other.id).get(organisation=self.organisation)
        self.assertEqual(new_programme.name, "Brand New Programme")
        self.assertEqual(new_programme.description, "")
        self.assertEqual(new_programme.need_and_background, "")
        self.assertRedirects(resp, reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": new_programme.id}))

    def test_clicking_new_programme_repeatedly_creates_independent_programmes(self):
        url = reverse("programmes:list", kwargs={"slug": self.organisation.slug})
        self.client.post(url, {"name": "Programme One", "status": Programme.STATUS_PLANNED})
        self.client.post(url, {"name": "Programme Two", "status": Programme.STATUS_PLANNED})
        names = set(Programme.objects.filter(organisation=self.organisation).values_list("name", flat=True))
        self.assertEqual(names, {"Programme One", "Programme Two"})

    def test_incomplete_programmes_show_directly_in_the_list_no_wizard_routing(self):
        programme = Programme.objects.create(organisation=self.organisation, name="Incomplete Programme")
        resp = self.client.get(reverse("programmes:list", kwargs={"slug": self.organisation.slug}))
        self.assertContains(resp, "Incomplete Programme")
        self.assertContains(resp, reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": programme.id}))

    def test_a_programme_is_progressively_completed_through_the_workspace(self):
        """Plan tab, M&E tab and the standalone Projects page -- not
        wizard steps -- are where a Programme's need/purpose/
        beneficiaries/geography/logic/first Project get filled in."""
        resp = self.client.post(reverse("programmes:list", kwargs={"slug": self.organisation.slug}), {
            "name": "Youth Digital Literacy Initiative", "status": Programme.STATUS_PLANNED,
        })
        programme = Programme.objects.get(organisation=self.organisation)

        self.client.post(reverse("programmes:plan", kwargs={"slug": self.organisation.slug, "programme_id": programme.id}), {
            "need_and_background": "Limited access to digital skills training.",
            "theory_of_change_summary": "Improve employability.",
            "target_beneficiary_groups": "Youth aged 18-35, Unemployed graduates",
            "locations": "Khayelitsha, Ekurhuleni", "programme_area": "education_skills",
        })
        programme.refresh_from_db()
        self.assertEqual(programme.need_and_background, "Limited access to digital skills training.")
        self.assertEqual(programme.target_beneficiary_groups, ["Youth aged 18-35", "Unemployed graduates"])
        self.assertEqual(programme.locations, ["Khayelitsha", "Ekurhuleni"])

        me_url = reverse("monitoring_evaluation:programme_me", kwargs={"slug": self.organisation.slug, "programme_id": programme.id})
        self.client.post(me_url, {"add_outcome": "1", "title": "Improved digital literacy", "description": ""})
        outcome = programme.outcomes.get()
        self.client.post(me_url, {"add_output": "1", "title": "Digital skills training delivered", "description": "", "outcome": str(outcome.id)})
        output = programme.outputs.get()
        self.client.post(me_url, {
            "add_indicator": "1", "name": "Young people completing training", "indicator_type": "count",
            "outcome": str(outcome.id), "output": str(output.id), "target_value": "100",
        })
        self.assertTrue(programme.indicators.filter(target_value=100).exists())
        self.assertTrue(compute_programme_readiness(programme)["is_ready"])

        self.client.post(reverse("projects:list", kwargs={"slug": self.organisation.slug}), {
            "name": "Digital Skills Bootcamp", "programme": str(programme.id), "status": Project.STATUS_ACTIVE, "budget": "65000",
        })
        self.assertTrue(Project.objects.filter(programme=programme, name="Digital Skills Bootcamp").exists())

    def test_non_manager_cannot_create_a_programme(self):
        other = User.objects.create_user(email="member@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=other, role="fundraiser")
        self.client.force_login(other)
        resp = self.client.post(reverse("programmes:list", kwargs={"slug": self.organisation.slug}), {
            "name": "Should not be created", "status": Programme.STATUS_PLANNED,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Programme.objects.filter(name="Should not be created").exists())


class ProgrammeWorkspaceOverviewTests(TestCase):
    """Every figure on the Overview tab must be a real database value --
    no fabricated progress, budget or attention items."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Youth Digital Literacy")

    def test_overview_counts_match_real_data(self):
        project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp", budget=65000)
        Activity.objects.create(programme=self.programme, name="Workshop", scheduled_date="2099-01-01")
        Outcome.objects.create(programme=self.programme, title="Improved literacy")

        resp = self.client.get(reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertEqual(resp.context["project_count"], 1)
        self.assertEqual(resp.context["activity_count"], 1)
        self.assertEqual(resp.context["outcome_count"], 1)
        self.assertEqual(resp.context["budget"]["budget"], 65000)
        self.assertEqual(resp.context["budget"]["spent"], 0)
        self.assertContains(resp, "Bootcamp")
        self.assertContains(resp, "Workshop")

    def test_no_add_activity_form_on_the_default_overview_page(self):
        resp = self.client.get(reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertNotContains(resp, 'name="scheduled_date"')

    def test_progress_is_none_when_no_indicator_results_exist(self):
        self.assertIsNone(compute_programme_progress(self.programme))
        resp = self.client.get(reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertContains(resp, "No indicator results recorded yet.")

    def test_progress_reflects_real_indicator_achievement(self):
        indicator = Indicator.objects.create(programme=self.programme, name="Youth trained", target_value=100)
        IndicatorPeriodValue.objects.create(indicator=indicator, period_start="2026-01-01", period_end="2026-01-31", actual_value=50)
        self.assertEqual(compute_programme_progress(self.programme), 50.0)

    def test_attention_list_reflects_real_gaps(self):
        attention = compute_programme_attention(self.programme, self.organisation)
        texts = [item["text"] for item in attention]
        self.assertIn("Add a programme outcome.", texts)
        self.assertIn("Add a project.", texts)
        self.assertIn("Add an activity.", texts)

        Outcome.objects.create(programme=self.programme, title="Improved literacy")
        Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp")
        Activity.objects.create(programme=self.programme, name="Workshop")
        attention = compute_programme_attention(self.programme, self.organisation)
        texts = [item["text"] for item in attention]
        self.assertNotIn("Add a programme outcome.", texts)
        self.assertNotIn("Add a project.", texts)
        self.assertNotIn("Add an activity.", texts)

    def test_budget_summary_rolls_up_across_projects_and_only_counts_approved_expenses(self):
        from apps.expenses.models import Expense

        project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp", budget=1000)
        Expense.objects.create(
            organisation=self.organisation, project=project, submitted_by=self.user,
            amount=200, description="Venue", status=Expense.STATUS_APPROVED,
        )
        Expense.objects.create(
            organisation=self.organisation, project=project, submitted_by=self.user,
            amount=999, description="Rejected", status=Expense.STATUS_REJECTED,
        )
        summary = programme_budget_summary(self.programme)
        self.assertEqual(summary["budget"], 1000)
        self.assertEqual(summary["spent"], 200)
        self.assertEqual(summary["remaining"], 800)

    def test_plan_tab_shows_and_edits_real_fields(self):
        url = reverse("programmes:plan", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(url, {
            "need_and_background": "Real need.", "theory_of_change_summary": "Real purpose.",
            "target_beneficiary_groups": "Youth, Adults", "locations": "Soweto",
            "start_date": "2026-01-01", "end_date": "2026-12-31", "staffing_plan": "One coordinator.",
        })
        self.assertRedirects(resp, url)
        self.programme.refresh_from_db()
        self.assertEqual(self.programme.need_and_background, "Real need.")
        self.assertEqual(self.programme.target_beneficiary_groups, ["Youth", "Adults"])
        self.assertEqual(self.programme.locations, ["Soweto"])

    def test_programme_list_shows_real_progress_column(self):
        indicator = Indicator.objects.create(programme=self.programme, name="Youth trained", target_value=100)
        IndicatorPeriodValue.objects.create(indicator=indicator, period_start="2026-01-01", period_end="2026-01-31", actual_value=75)
        resp = self.client.get(reverse("programmes:list", kwargs={"slug": self.organisation.slug}))
        row = next(r for r in resp.context["rows"] if r["programme"] == self.programme)
        self.assertEqual(row["progress"], 75.0)


class ActivityCreationTests(TestCase):
    """Progressive context inheritance: creating an activity from inside a
    project must pre-fill programme/project/location/manager silently, and
    scope the outputs/budget_line choices to that programme/project --
    never a blank, unscoped picker."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Youth Digital Literacy")
        self.manager = User.objects.create_user(email="manager@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.manager, role=ORG_ROLE_ADMIN)
        self.project = Project.objects.create(
            organisation=self.organisation, programme=self.programme, name="Bootcamp",
            manager=self.manager,
        )

    def test_create_activity_from_project_prefills_context(self):
        url = reverse("programmes:create_activity", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})
        resp = self.client.get(url, {"project": str(self.project.id)})
        form = resp.context["form"]
        self.assertEqual(form.fields["responsible_person"].initial, self.manager.id)
        self.assertEqual(form.fields["project"].initial, self.project.id)

    def test_create_activity_saves_and_links_project(self):
        url = reverse("programmes:create_activity", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})
        resp = self.client.post(url, {"project": str(self.project.id)}, QUERY_STRING=f"project={self.project.id}")
        # Resubmit as a real POST with the form fields required.
        resp = self.client.post(
            f"{url}?project={self.project.id}",
            {"name": "HTML & CSS Workshop", "status": "planned", "project": str(self.project.id), "location": "Khayelitsha", "outputs": []},
        )
        activity = Activity.objects.get(name="HTML & CSS Workshop")
        self.assertEqual(activity.programme, self.programme)
        self.assertEqual(activity.project, self.project)
        self.assertRedirects(resp, reverse("programmes:activities", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))

    def test_budget_line_choices_are_scoped_to_the_projects_own_budget(self):
        other_project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Other")
        own_budget = Budget.objects.create(project=self.project)
        own_line = BudgetLine.objects.create(budget=own_budget, category="Venue", allocated_amount=1000)
        other_budget = Budget.objects.create(project=other_project)
        BudgetLine.objects.create(budget=other_budget, category="Transport", allocated_amount=500)

        url = reverse("programmes:create_activity", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})
        resp = self.client.get(url, {"project": str(self.project.id)})
        budget_line_choices = list(resp.context["form"].fields["budget_line"].queryset)
        self.assertEqual(budget_line_choices, [own_line])


class ProjectProgrammeFilterTests(TestCase):
    """The Programme Workspace's Projects tab reuses projects:list with a
    ?programme= filter rather than a duplicate view."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Programme A")
        self.other_programme = Programme.objects.create(organisation=self.organisation, name="Programme B")
        self.project_in = Project.objects.create(organisation=self.organisation, programme=self.programme, name="In Programme")
        self.project_out = Project.objects.create(organisation=self.organisation, programme=self.other_programme, name="Other Programme")

    def test_programme_filter_only_shows_that_programmes_projects(self):
        resp = self.client.get(reverse("projects:list", kwargs={"slug": self.organisation.slug}), {"programme": str(self.programme.id)})
        projects = list(resp.context["projects"])
        self.assertIn(self.project_in, projects)
        self.assertNotIn(self.project_out, projects)


class ModalPatternTests(TestCase):
    """Tables show data; create forms stay inside a closed modal until the
    trigger button is clicked, and re-open themselves only on a failed
    validation -- mirrors apps.projects.tests.ModalPatternTests."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Youth Digital Literacy")

    def test_activities_tab_modal_closed_by_default_and_opens_on_error(self):
        url = reverse("programmes:activities", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})
        resp = self.client.get(url)
        self.assertContains(resp, 'data-modal-open="activity-modal"')
        self.assertNotContains(resp, 'data-open-on-load="true"')

        resp = self.client.post(url, {"name": "", "status": "planned", "location": "A specific venue"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-open-on-load="true"')
        self.assertContains(resp, "A specific venue")

    def test_activity_created_via_the_tab_modal_is_saved_and_shown(self):
        url = reverse("programmes:activities", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})
        resp = self.client.post(url, {"name": "Coding Club", "status": "planned"})
        self.assertRedirects(resp, url)
        self.assertTrue(Activity.objects.filter(programme=self.programme, name="Coding Club").exists())

    def test_evidence_tab_modal_closed_by_default(self):
        url = reverse("programmes:evidence", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})
        resp = self.client.get(url)
        self.assertContains(resp, 'data-modal-open="evidence-modal"')
        self.assertNotContains(resp, 'data-open-on-load="true"')


class ActivityCRUDTests(TestCase):
    """Create/Read already covered elsewhere -- this covers Update/Delete,
    which UAT flagged as missing."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Programme")
        self.activity = Activity.objects.create(programme=self.programme, name="Workshop", status="planned")

    def test_edit_activity_updates_real_fields(self):
        url = reverse("programmes:edit_activity", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "activity_id": self.activity.id,
        })
        resp = self.client.post(url, {"name": "Renamed Workshop", "status": "delivered", "location": "Hall B"})
        self.assertRedirects(resp, reverse("programmes:activities", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.name, "Renamed Workshop")
        self.assertEqual(self.activity.status, "delivered")
        self.assertEqual(self.activity.location, "Hall B")

    def test_delete_activity_requires_post_and_confirmation_page_on_get(self):
        url = reverse("programmes:delete_activity", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "activity_id": self.activity.id,
        })
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Activity.objects.filter(id=self.activity.id).exists())  # not deleted by GET

        resp = self.client.post(url)
        self.assertRedirects(resp, reverse("programmes:activities", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertFalse(Activity.objects.filter(id=self.activity.id).exists())

    def test_deleting_an_activity_with_a_project_redirects_to_the_project(self):
        project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp")
        activity = Activity.objects.create(programme=self.programme, project=project, name="Session")
        url = reverse("programmes:delete_activity", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "activity_id": activity.id,
        })
        resp = self.client.post(url)
        self.assertRedirects(resp, reverse("projects:activities", kwargs={"slug": self.organisation.slug, "project_id": project.id}))

    def test_non_manager_cannot_edit_or_delete_activity(self):
        other = User.objects.create_user(email="member@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=other, role="fundraiser")
        self.client.force_login(other)
        edit_url = reverse("programmes:edit_activity", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "activity_id": self.activity.id,
        })
        delete_url = reverse("programmes:delete_activity", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "activity_id": self.activity.id,
        })
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.assertTrue(Activity.objects.filter(id=self.activity.id).exists())


class ProgrammeGeographyAndSectorTests(TestCase):
    """Province is a controlled SA province list (reused from
    Organisation); Locations stays free-text for finer geography
    (district/municipality/locality/venue) -- neither level is forced.
    Programme area/sector is a controlled, extensible list."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Programme")

    def test_province_alone_satisfies_geography_readiness(self):
        self.programme.province = "GP"
        self.programme.save()
        self.assertTrue(
            dict(compute_programme_readiness(self.programme)["checks"])["Geography defined"]
        )

    def test_locations_alone_still_satisfies_geography_readiness(self):
        self.programme.locations = ["Khayelitsha"]
        self.programme.save()
        self.assertTrue(
            dict(compute_programme_readiness(self.programme)["checks"])["Geography defined"]
        )

    def test_plan_tab_can_set_province_and_sector(self):
        url = reverse("programmes:plan", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})
        resp = self.client.post(url, {
            "programme_area": "youth_development", "province": "GP",
            "need_and_background": "", "theory_of_change_summary": "",
            "target_beneficiary_groups": "", "locations": "",
        })
        self.assertRedirects(resp, url)
        self.programme.refresh_from_db()
        self.assertEqual(self.programme.province, "GP")
        self.assertEqual(self.programme.programme_area, "youth_development")
        resp = self.client.get(url)
        self.assertContains(resp, "Gauteng")
        self.assertContains(resp, "Youth Development")


class ProgrammeReadinessTests(TestCase):
    """A Programme must reach minimum planning readiness before a Project
    can be created under it -- a checklist gate, not a percentage, and
    funding is deliberately excluded from it."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Bare Programme")

    def _make_ready(self):
        self.programme.need_and_background = "A real need."
        self.programme.theory_of_change_summary = "A real purpose."
        self.programme.target_beneficiary_groups = ["Youth"]
        self.programme.locations = ["Katlehong"]
        self.programme.save()
        outcome = Outcome.objects.create(programme=self.programme, title="Outcome")
        output = Output.objects.create(programme=self.programme, outcome=outcome, title="Output")
        Indicator.objects.create(programme=self.programme, outcome=outcome, output=output, name="Indicator", target_value=100)

    def test_bare_programme_is_not_ready(self):
        readiness = compute_programme_readiness(self.programme)
        self.assertFalse(readiness["is_ready"])
        self.assertIn("Outcome defined", readiness["missing"])
        self.assertIn("Target defined", readiness["missing"])

    def test_fully_planned_programme_is_ready(self):
        self._make_ready()
        readiness = compute_programme_readiness(self.programme)
        self.assertTrue(readiness["is_ready"])
        self.assertEqual(readiness["missing"], [])

    def test_funding_is_not_part_of_the_readiness_gate(self):
        # Section 4: "Funding can be tracked separately and should not
        # make an otherwise valid Programme impossible to plan."
        self._make_ready()
        readiness = compute_programme_readiness(self.programme)
        labels = [label for label, _met in readiness["checks"]]
        self.assertNotIn("Funding identified", labels)
        self.assertTrue(readiness["is_ready"])  # ready with zero grants linked

    def test_project_creation_is_blocked_for_an_unready_programme(self):
        form = ProjectForm(
            {"name": "Bootcamp", "programme": str(self.programme.id), "status": Project.STATUS_PLANNING, "budget": "0"},
            organisation=self.organisation,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("programme", form.errors)

    def test_project_creation_is_allowed_once_ready(self):
        self._make_ready()
        form = ProjectForm(
            {"name": "Bootcamp", "programme": str(self.programme.id), "status": Project.STATUS_PLANNING, "budget": "0"},
            organisation=self.organisation,
        )
        self.assertTrue(form.is_valid())

    def test_editing_an_already_linked_project_is_never_blocked_by_readiness(self):
        self._make_ready()
        project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp")
        readiness = compute_programme_readiness(self.programme)
        self.assertTrue(readiness["is_ready"])
        # Programme regresses (e.g. an indicator gets removed) -- editing
        # the already-linked project must still work.
        self.programme.indicators.all().delete()
        form = ProjectForm(
            {"name": "Bootcamp Renamed", "programme": str(self.programme.id), "status": Project.STATUS_ACTIVE, "budget": "0"},
            instance=project, organisation=self.organisation,
        )
        self.assertTrue(form.is_valid())

    def test_standalone_project_create_view_is_blocked_until_ready(self):
        resp = self.client.post(reverse("projects:list", kwargs={"slug": self.organisation.slug}), {
            "name": "Bootcamp", "programme": str(self.programme.id), "status": Project.STATUS_ACTIVE, "budget": "0",
        })
        self.assertFalse(Project.objects.filter(programme=self.programme).exists())
        self.assertContains(resp, "Complete the Programme Plan first")

        self._make_ready()
        resp = self.client.post(reverse("projects:list", kwargs={"slug": self.organisation.slug}), {
            "name": "Bootcamp", "programme": str(self.programme.id), "status": Project.STATUS_ACTIVE, "budget": "0",
        })
        self.assertTrue(Project.objects.filter(programme=self.programme, name="Bootcamp").exists())

    def test_programme_overview_shows_the_readiness_path(self):
        resp = self.client.get(reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertContains(resp, "Programme not ready")
        self.assertContains(resp, "1 / 11 complete")  # "Programme defined" is already met (it has a name)
        self._make_ready()
        resp = self.client.get(reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertContains(resp, "Programme ready")
        self.assertContains(resp, "9 / 11 complete")
        # Each step routes straight to where it's edited.
        self.assertContains(resp, reverse("programmes:plan", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertContains(resp, reverse("monitoring_evaluation:programme_me", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertContains(resp, reverse("programmes:team", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))


class ProgrammeTeamTests(TestCase):
    """The Programme Team is who is responsible for delivering it --
    distinct from the organisation's general membership and from
    beneficiaries reached."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.manager = User.objects.create_user(email="manager@example.com", password=PASSWORD, first_name="Thabiso")
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.manager, role=ORG_ROLE_ADMIN)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Youth Digital Skills")
        self.url = reverse("programmes:team", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id})

    def test_add_programme_manager_references_the_existing_user(self):
        resp = self.client.post(self.url, {"user": str(self.manager.id), "role": "programme_manager", "status": "active"})
        self.assertRedirects(resp, self.url)
        from apps.programmes.models import ProgrammeMembership

        membership = ProgrammeMembership.objects.get(programme=self.programme)
        self.assertEqual(membership.user_id, self.manager.id)
        self.assertEqual(User.objects.count(), 2)

    def test_someone_outside_the_organisation_cannot_be_added(self):
        from apps.programmes.forms import ProgrammeMembershipForm

        outsider = User.objects.create_user(email="outsider@example.com", password=PASSWORD)
        form = ProgrammeMembershipForm(
            {"user": str(outsider.id), "role": "volunteer", "status": "active"},
            organisation=self.organisation, programme=self.programme,
        )
        self.assertFalse(form.is_valid())

    def test_programme_manager_assigned_satisfies_the_recommended_readiness_check(self):
        self.assertIn(
            "Programme Manager assigned",
            compute_programme_readiness(self.programme)["recommended_missing"],
        )
        from apps.programmes.models import ProgrammeMembership

        ProgrammeMembership.objects.create(programme=self.programme, user=self.manager, role="programme_manager")
        self.assertNotIn(
            "Programme Manager assigned",
            compute_programme_readiness(self.programme)["recommended_missing"],
        )

    def test_programme_overview_shows_the_team_summary(self):
        from apps.programmes.models import ProgrammeMembership

        ProgrammeMembership.objects.create(programme=self.programme, user=self.manager, role="programme_manager")
        resp = self.client.get(reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertContains(resp, "Programme Manager: Thabiso")


class DOPADemonstrationScenarioTests(TestCase):
    """The full DOPA demonstration scenario end to end, through the real
    views a user actually clicks through -- not direct model creation.
    This is the capstone: Organisation -> Programme (wizard) -> Outcome
    -> Output -> Indicator -> Target -> Programme Team -> two Projects
    -> Activities -> Tasks -> Project Team -> Budget -> Expense
    (submitted -> approved), with the exact Committed/Actual/Remaining
    figures checked at each stage."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="DOPA", organisation_type="npo")
        self.admin = User.objects.create_user(email="admin@dopa.example.com", password=PASSWORD, first_name="Thabiso")
        self.reviewer = User.objects.create_user(email="finance@dopa.example.com", password=PASSWORD, first_name="Sarah")
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.admin, role=ORG_ROLE_ADMIN)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.reviewer, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.admin)

    def test_full_dopa_scenario(self):
        from apps.expenses.models import Budget, BudgetLine, Expense
        from apps.programmes.models import ProgrammeMembership
        from apps.projects.models import ProjectMembership

        slug = self.organisation.slug

        # 1. Programme -- a short create form, not a wizard.
        resp = self.client.post(reverse("programmes:list", kwargs={"slug": slug}), {
            "name": "DOPA Youth Digital Skills & Employability Programme",
            "programme_area": "education_skills", "status": Programme.STATUS_PLANNED,
        })
        programme = Programme.objects.get(organisation=self.organisation)
        self.assertRedirects(resp, reverse("programmes:detail", kwargs={"slug": slug, "programme_id": programme.id}))

        # Filled in progressively on the Plan tab -- one form, not three
        # separate wizard steps (need/purpose, who/where, staffing all live
        # together there now).
        self.client.post(reverse("programmes:plan", kwargs={"slug": slug, "programme_id": programme.id}), {
            "need_and_background": "Young people in Katlehong and surrounding rural communities have limited access to digital skills training and struggle to enter the job market.",
            "theory_of_change_summary": "If young people gain practical digital and workplace-readiness skills, they will be more employable.",
            "target_beneficiary_groups": "Unemployed youth aged 18-30",
            "province": "GP", "locations": "Katlehong", "programme_area": "education_skills",
            "staffing_plan": "One programme manager, one facilitator.",
        })
        programme.refresh_from_db()

        # 2. Outcome -> Output -> Indicator -> Target, via the small M&E popups.
        me_url = reverse("monitoring_evaluation:programme_me", kwargs={"slug": slug, "programme_id": programme.id})
        self.client.post(me_url, {
            "add_outcome": "1", "title": "Young people improve their digital skills and workplace readiness.", "description": "",
        })
        outcome = programme.outcomes.get()
        self.client.post(me_url, {
            "add_output": "1", "title": "Digital skills training delivered.", "description": "", "outcome": str(outcome.id),
        })
        output = programme.outputs.get()
        self.client.post(me_url, {
            "add_indicator": "1", "name": "Young people completing digital skills training.",
            "indicator_type": "count", "outcome": str(outcome.id), "output": str(output.id), "target_value": "100",
        })
        programme.refresh_from_db()

        readiness = compute_programme_readiness(programme)
        self.assertTrue(readiness["is_ready"], readiness["missing"])

        # 3. Project 1, via the standalone Projects page -- now unblocked.
        self.client.post(reverse("projects:list", kwargs={"slug": slug}), {
            "name": "Digital Skills Bootcamp – Katlehong", "programme": str(programme.id), "status": Project.STATUS_ACTIVE,
            "budget": "20000",
        })
        project1 = Project.objects.get(programme=programme, name__contains="Katlehong")

        # Activities, via the Programme's own Activities tab.
        activities_url = reverse("programmes:activities", kwargs={"slug": slug, "programme_id": programme.id})
        self.client.post(activities_url, {"name": "Computer & Digital Literacy Workshop", "status": "planned", "project": str(project1.id)})
        self.client.post(activities_url, {"name": "CV & Workplace Readiness Workshop", "status": "planned", "project": str(project1.id)})
        self.assertEqual(project1.activities.count(), 2)

        # 4. Programme Team.
        self.client.post(reverse("programmes:team", kwargs={"slug": slug, "programme_id": programme.id}), {
            "user": str(self.admin.id), "role": "programme_manager", "status": "active",
        })
        self.assertTrue(ProgrammeMembership.objects.filter(programme=programme, user=self.admin, role="programme_manager").exists())

        # 5. Project 2, from the Projects list -- the Programme is ready, so this is unblocked too.
        resp = self.client.post(reverse("projects:list", kwargs={"slug": slug}), {
            "name": "Digital Skills Bootcamp – Rural School", "programme": str(programme.id), "status": Project.STATUS_PLANNING, "budget": "0",
        })
        self.assertEqual(Project.objects.filter(programme=programme).count(), 2)

        # 6. Tasks on Project 1.
        for title in ["Book training venue", "Arrange computers", "Confirm facilitator", "Print attendance register"]:
            self.client.post(reverse("projects:tasks", kwargs={"slug": slug, "project_id": project1.id}), {"title": title, "status": "todo"})
        self.assertEqual(project1.tasks.count(), 4)

        # 7. Project Team.
        self.client.post(reverse("projects:people", kwargs={"slug": slug, "project_id": project1.id}), {
            "user": str(self.admin.id), "role": "project_manager", "status": "active",
        })
        self.assertTrue(ProjectMembership.objects.filter(project=project1, user=self.admin, role="project_manager").exists())

        # 8. Budget: R20,000 with the real line breakdown.
        self.client.post(reverse("projects:budget", kwargs={"slug": slug, "project_id": project1.id}), {
            "create_budget": "1", "total_amount": "20000",
        })
        budget = Budget.objects.get(project=project1)
        self.assertEqual(budget.total_amount, 20000)
        lines = {"Facilitator": "4000", "Venue": "5000", "Refreshments": "4000", "Training materials": "3000", "Transport": "2000", "Printing": "2000"}
        for category, amount in lines.items():
            self.client.post(reverse("projects:budget", kwargs={"slug": slug, "project_id": project1.id}), {
                "add_line": "1", "category": category, "allocated_amount": amount,
            })
        self.assertEqual(budget.lines.count(), 6)
        self.assertEqual(sum(l.allocated_amount for l in budget.lines.all()), 20000)

        # 9. Submit the Facilitator expense -- Committed, not yet Actual.
        facilitator_line = budget.lines.get(category="Facilitator")
        self.client.post(reverse("projects:expenses", kwargs={"slug": slug, "project_id": project1.id}), {
            "budget_line": str(facilitator_line.id), "amount": "4000", "description": "Facilitator",
            "receipt": SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
        })
        expense = Expense.objects.get(project=project1)
        self.assertEqual(expense.status, Expense.STATUS_SUBMITTED)

        summary = project_finance_summary(project1)
        self.assertEqual(summary["planned"], 20000)
        self.assertEqual(summary["committed"], 4000)
        self.assertEqual(summary["actual"], 0)
        self.assertEqual(summary["remaining"], 20000)

        # 10. A different reviewer approves it -- Actual, no longer Committed,
        # never double-counted.
        self.client.force_login(self.reviewer)
        self.client.post(reverse("expenses:review_expense", kwargs={"slug": slug, "expense_id": expense.id}), {
            "status": Expense.STATUS_APPROVED, "review_note": "Approved.",
        })
        summary = project_finance_summary(project1)
        self.assertEqual(summary["planned"], 20000)
        self.assertEqual(summary["committed"], 0)
        self.assertEqual(summary["actual"], 4000)
        self.assertEqual(summary["remaining"], 16000)

        # 11. Completing the project doesn't change its finance.
        project1.status = Project.STATUS_COMPLETE
        project1.save()
        summary = project_finance_summary(project1)
        self.assertEqual(summary["actual"], 4000)
        self.assertEqual(summary["remaining"], 16000)

        # 12. Theory of Change, an Assumption and a Learning Question --
        # the Programme Logic & Learning layer, informational only.
        self.client.force_login(self.admin)
        self.client.post(reverse("programmes:plan", kwargs={"slug": slug, "programme_id": programme.id}), {
            "save_toc": "1",
            "toc_what": "Young people receive practical digital skills training.",
            "toc_change": "Their digital skills and workplace readiness improve.",
            "toc_why": "They receive relevant training, practise the skills and receive support applying them.",
        })
        programme.refresh_from_db()
        self.assertEqual(programme.toc_change, "Their digital skills and workplace readiness improve.")

        self.client.post(reverse("programmes:plan", kwargs={"slug": slug, "programme_id": programme.id}), {
            "add_assumption": "1",
            "statement": "Participants have sufficient access to devices to practise the skills.",
            "importance": "high", "status": "active", "note": "",
        })
        self.assertTrue(programme.assumptions.filter(importance="high").exists())

        self.client.post(reverse("programmes:learning", kwargs={"slug": slug, "programme_id": programme.id}), {
            "add_learning_question": "1",
            "question": "What type of digital skills training most improves workplace readiness?",
            "why_it_matters": "", "status": "open", "answer_note": "",
        })
        self.assertTrue(programme.learning_questions.exists())

        readiness = compute_programme_readiness(programme)
        self.assertTrue(readiness["is_ready"])  # Logic & Learning never blocks the gate
        learning_labels = dict(readiness["logic_and_learning"])
        self.assertTrue(learning_labels["Theory of Change considered"])
        self.assertTrue(learning_labels["Key assumptions identified"])
        self.assertTrue(learning_labels["Learning question identified"])
        self.assertIn("At least one project created", dict(readiness["recommended"]))

        # 13. Record the actual against the Target=100 indicator: 63
        # completed. A miss is not treated as failure -- the form lets the
        # team explain it.
        indicator = programme.indicators.get()
        self.client.post(reverse("monitoring_evaluation:indicator_detail", kwargs={"slug": slug, "indicator_id": indicator.id}), {
            "period_start": "2026-01-01", "period_end": "2026-03-31", "actual_value": "63",
            "contributing_factors": "Saturday sessions had lower attendance than expected.",
            "learning_note": "Saturday sessions clash with part-time work for many participants.",
            "action_needed": "Move future sessions to weekday afternoons and add attendance reminders.",
        })
        period_value = indicator.period_values.get()
        self.assertEqual(period_value.actual_value, 63)
        self.assertEqual(indicator.achievement_percent, 63.0)
        self.assertIn("weekday afternoons", period_value.action_needed)

        # 14. Record the learning moment in the Learning Log, tied to the
        # project and activity it relates to, with evidence reused from
        # the Programme's own Evidence library (never a fresh upload).
        content_type = ContentType.objects.get_for_model(Programme)
        evidence_doc = Document.objects.create(
            organisation=self.organisation, title="Attendance register", category=Document.CATEGORY_PROGRAMMES,
            file=SimpleUploadedFile("register.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
            uploaded_by=self.admin, content_type=content_type, object_id=str(programme.id),
        )
        activity = project1.activities.get(name__contains="Computer")
        self.client.post(reverse("programmes:learning", kwargs={"slug": slug, "programme_id": programme.id}), {
            "add_learning_log": "1", "date": "2026-03-31", "project": str(project1.id), "activity": str(activity.id),
            "entry_type": "challenge",
            "what_happened": "Only 63 of the expected 100 participants completed the programme.",
            "what_changed": "", "what_we_learned": "Saturday sessions had lower attendance because many participants were working.",
            "action_we_will_take": "Move the next training session to weekday afternoons.",
            "evidence": str(evidence_doc.id),
        })
        entry = programme.learning_log_entries.get()
        self.assertEqual(entry.project_id, project1.id)
        self.assertEqual(entry.evidence_id, evidence_doc.id)
        self.assertEqual(entry.recorded_by_id, self.admin.id)

        # 15. Money -> Activity -> Output -> Result -> Evidence stays
        # traceable through existing links -- Finance Light, not a new
        # accounting system.
        activity.budget_line = facilitator_line
        activity.outputs.add(output)
        activity.save()
        self.assertEqual(activity.budget_line.category, "Facilitator")
        self.assertEqual(activity.budget_line.expenses.get().status, Expense.STATUS_APPROVED)
        self.assertIn(output, activity.outputs.all())
        self.assertEqual(output.indicators.get(), indicator)
        self.assertEqual(entry.evidence.title, "Attendance register")


class ProgrammeLearningLayerCRUDTests(TestCase):
    """Edit/delete for Assumptions, Learning Questions, Learning Log
    entries and Context Notes -- no silent deletion, and a non-manager
    can't add or remove any of them."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.manager = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.manager, role=ORG_ROLE_ADMIN)
        self.outsider = User.objects.create_user(email="outsider@example.com", password=PASSWORD)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Youth Digital Skills")
        self.client.force_login(self.manager)

    def test_assumption_edit_and_delete(self):
        from apps.programmes.models import Assumption

        assumption = Assumption.objects.create(
            programme=self.programme, statement="Participants have access to devices.",
            importance=Assumption.IMPORTANCE_HIGH, status=Assumption.STATUS_ACTIVE,
        )
        edit_url = reverse("programmes:assumption_edit", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "assumption_id": assumption.id,
        })
        self.client.post(edit_url, {
            "statement": assumption.statement, "importance": "medium", "status": "being_tested", "note": "Checking now.",
        })
        assumption.refresh_from_db()
        self.assertEqual(assumption.status, Assumption.STATUS_BEING_TESTED)

        delete_url = reverse("programmes:assumption_delete", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "assumption_id": assumption.id,
        })
        get_resp = self.client.get(delete_url)
        self.assertEqual(get_resp.status_code, 200)  # confirmation page, not an immediate delete
        self.assertTrue(Assumption.objects.filter(id=assumption.id).exists())
        self.client.post(delete_url)
        self.assertFalse(Assumption.objects.filter(id=assumption.id).exists())

    def test_learning_question_edit_and_delete(self):
        from apps.programmes.models import LearningQuestion

        question = LearningQuestion.objects.create(programme=self.programme, question="What works best?")
        edit_url = reverse("programmes:learning_question_edit", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "question_id": question.id,
        })
        self.client.post(edit_url, {
            "question": question.question, "why_it_matters": "", "status": "answered", "answer_note": "Weekday afternoons work best.",
        })
        question.refresh_from_db()
        self.assertEqual(question.status, LearningQuestion.STATUS_ANSWERED)
        self.assertEqual(question.answer_note, "Weekday afternoons work best.")

        delete_url = reverse("programmes:learning_question_delete", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "question_id": question.id,
        })
        self.client.post(delete_url)
        self.assertFalse(LearningQuestion.objects.filter(id=question.id).exists())

    def test_context_note_add_edit_delete(self):
        from apps.programmes.models import ContextNote

        self.client.post(reverse("programmes:learning", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}), {
            "add_context_note": "1", "category": "venue", "description": "Usual venue booked out for the next term.", "date": "2026-06-01",
        })
        note = ContextNote.objects.get(programme=self.programme)
        self.assertEqual(note.category, "venue")

        edit_url = reverse("programmes:context_note_edit", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "note_id": note.id,
        })
        self.client.post(edit_url, {"category": "venue", "description": "Backup venue confirmed.", "date": "2026-06-05"})
        note.refresh_from_db()
        self.assertEqual(note.description, "Backup venue confirmed.")

        delete_url = reverse("programmes:context_note_delete", kwargs={
            "slug": self.organisation.slug, "programme_id": self.programme.id, "note_id": note.id,
        })
        self.client.post(delete_url)
        self.assertFalse(ContextNote.objects.filter(id=note.id).exists())

    def test_outsider_cannot_add_or_edit_assumptions(self):
        from apps.programmes.models import Assumption

        self.client.force_login(self.outsider)
        resp = self.client.post(reverse("programmes:plan", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}), {
            "add_assumption": "1", "statement": "Should not be allowed.", "importance": "low", "status": "active", "note": "",
        })
        self.assertEqual(resp.status_code, 404)  # get_organisation_or_404_for_user denies access
        self.assertFalse(Assumption.objects.filter(programme=self.programme).exists())

    def test_readiness_recommends_a_project_before_any_exist(self):
        readiness = compute_programme_readiness(self.programme)
        self.assertIn("At least one project created", readiness["recommended_missing"])
        self.assertFalse(readiness["is_ready"])  # foundation/logic still incomplete on a bare programme

    def test_theory_of_change_all_three_fields_required_to_count_as_considered(self):
        self.programme.toc_what = "Something"
        self.programme.toc_change = "Something else"
        self.programme.save()
        readiness = compute_programme_readiness(self.programme)
        self.assertFalse(dict(readiness["logic_and_learning"])["Theory of Change considered"])
        self.programme.toc_why = "Because reasons"
        self.programme.save()
        readiness = compute_programme_readiness(self.programme)
        self.assertTrue(dict(readiness["logic_and_learning"])["Theory of Change considered"])
