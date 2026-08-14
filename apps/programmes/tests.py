from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import ORG_ROLE_ADMIN
from apps.expenses.models import Budget, BudgetLine
from apps.monitoring_evaluation.models import Indicator, IndicatorPeriodValue, Outcome
from apps.organisations.models import Organisation, OrganisationMembership
from apps.programmes.models import Activity, Programme
from apps.programmes.services import compute_programme_attention, compute_programme_progress, programme_budget_summary
from apps.projects.models import Project

PASSWORD = "TestPass!2026"


class ProgrammeWizardGoldenPathTests(TestCase):
    """Every step of the guided wizard, mirroring the live UAT walkthrough:
    create -> Why -> Who & Where -> Success -> Projects & Activities ->
    People & Resources -> Budget & Funding -> Review -> Overview."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)

    def test_full_wizard_creates_a_complete_programme(self):
        resp = self.client.post(reverse("programmes:create", kwargs={"slug": self.organisation.slug}), {
            "name": "Youth Digital Literacy Initiative", "programme_area": "Education & Skills Development",
            "status": Programme.STATUS_PLANNED, "start_date": "2026-04-01", "end_date": "2027-03-31",
        })
        programme = Programme.objects.get(organisation=self.organisation)
        self.assertRedirects(
            resp, reverse("programmes:wizard_step", kwargs={
                "slug": self.organisation.slug, "programme_id": programme.id, "step": Programme.WIZARD_WHY,
            }),
        )
        self.assertEqual(programme.wizard_step, Programme.WIZARD_WHY)

        def wizard_url(step):
            return reverse("programmes:wizard_step", kwargs={"slug": self.organisation.slug, "programme_id": programme.id, "step": step})

        self.client.post(wizard_url(Programme.WIZARD_WHY), {
            "need_and_background": "Limited access to digital skills training.",
            "theory_of_change_summary": "Improve employability.",
        })
        programme.refresh_from_db()
        self.assertEqual(programme.wizard_step, Programme.WIZARD_WHO_AND_WHERE)

        self.client.post(wizard_url(Programme.WIZARD_WHO_AND_WHERE), {
            "target_beneficiary_groups": "Youth aged 18-35, Unemployed graduates",
            "locations": "Khayelitsha, Ekurhuleni",
        })
        programme.refresh_from_db()
        self.assertEqual(programme.wizard_step, Programme.WIZARD_SUCCESS)
        self.assertEqual(programme.target_beneficiary_groups, ["Youth aged 18-35", "Unemployed graduates"])
        self.assertEqual(programme.locations, ["Khayelitsha", "Ekurhuleni"])

        self.client.post(wizard_url(Programme.WIZARD_SUCCESS), {"add_outcome": "1", "title": "Improved digital literacy", "description": ""})
        self.assertEqual(programme.outcomes.count(), 1)
        self.client.post(wizard_url(Programme.WIZARD_SUCCESS), {"continue": "1"})
        programme.refresh_from_db()
        self.assertEqual(programme.wizard_step, Programme.WIZARD_PROJECTS_AND_ACTIVITIES)

        self.client.post(wizard_url(Programme.WIZARD_PROJECTS_AND_ACTIVITIES), {
            "add_project": "1", "name": "Digital Skills Bootcamp", "status": Project.STATUS_ACTIVE, "budget": "65000",
        })
        project = Project.objects.get(programme=programme)
        self.assertEqual(project.name, "Digital Skills Bootcamp")
        self.client.post(wizard_url(Programme.WIZARD_PROJECTS_AND_ACTIVITIES), {"continue": "1"})
        programme.refresh_from_db()
        self.assertEqual(programme.wizard_step, Programme.WIZARD_PEOPLE_AND_RESOURCES)

        self.client.post(wizard_url(Programme.WIZARD_PEOPLE_AND_RESOURCES), {"staffing_plan": "Two facilitators."})
        programme.refresh_from_db()
        self.assertEqual(programme.wizard_step, Programme.WIZARD_BUDGET_AND_FUNDING)
        self.assertEqual(programme.staffing_plan, "Two facilitators.")

        self.client.post(wizard_url(Programme.WIZARD_BUDGET_AND_FUNDING), {"grants": []})
        programme.refresh_from_db()
        self.assertEqual(programme.wizard_step, Programme.WIZARD_REVIEW)

        resp = self.client.post(wizard_url(Programme.WIZARD_REVIEW))
        programme.refresh_from_db()
        self.assertEqual(programme.wizard_step, Programme.WIZARD_COMPLETE)
        self.assertRedirects(resp, reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": programme.id}))

    def test_wizard_resumes_a_programme_genuinely_mid_wizard(self):
        programme = Programme.objects.create(
            organisation=self.organisation, name="Mid Wizard", wizard_step=Programme.WIZARD_WHY,
        )
        resp = self.client.get(reverse("programmes:create", kwargs={"slug": self.organisation.slug}))
        self.assertRedirects(resp, reverse("programmes:wizard_step", kwargs={
            "slug": self.organisation.slug, "programme_id": programme.id, "step": Programme.WIZARD_WHY,
        }))

    def test_pre_existing_programme_with_default_wizard_step_is_not_treated_as_mid_wizard(self):
        # Regression test: a programme created before the wizard existed
        # (or any programme whose wizard_step is still the field default)
        # must not be mistaken for an abandoned wizard -- that bug caused
        # an infinite redirect loop, caught via a live browser walkthrough.
        Programme.objects.create(organisation=self.organisation, name="Legacy Programme")
        resp = self.client.get(reverse("programmes:create", kwargs={"slug": self.organisation.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("wizard_step", resp.request["PATH_INFO"])

    def test_wizard_step_with_unrecognised_step_redirects_to_workspace_not_a_loop(self):
        programme = Programme.objects.create(organisation=self.organisation, name="Legacy Programme")
        resp = self.client.get(reverse("programmes:wizard_step", kwargs={
            "slug": self.organisation.slug, "programme_id": programme.id, "step": Programme.WIZARD_PROGRAMME,
        }))
        self.assertRedirects(resp, reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": programme.id}))

    def test_non_manager_cannot_create_a_programme(self):
        other = User.objects.create_user(email="member@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=other, role="fundraiser")
        self.client.force_login(other)
        resp = self.client.get(reverse("programmes:create", kwargs={"slug": self.organisation.slug}))
        self.assertEqual(resp.status_code, 403)


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
