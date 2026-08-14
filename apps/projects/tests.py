from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.beneficiaries.models import Beneficiary
from apps.core.permissions import ORG_ROLE_ADMIN
from apps.expenses.models import Budget, BudgetLine, Expense
from apps.organisations.models import Organisation, OrganisationMembership
from apps.programmes.models import Activity, Programme
from apps.projects.models import Project, ProjectTask
from apps.projects.services import (
    compute_project_attention,
    compute_project_progress,
    project_finance_summary,
    project_workspace_summary,
)

PASSWORD = "TestPass!2026"


class ProjectWorkspaceOverviewTests(TestCase):
    """Every figure on the Project Workspace Overview must be a real
    database value -- no fabricated progress, budget or attention items."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Youth Digital Literacy")
        self.project = Project.objects.create(
            organisation=self.organisation, programme=self.programme, name="Bootcamp", budget=1000,
        )

    def test_overview_status_200_and_shows_real_project_name(self):
        resp = self.client.get(reverse("projects:detail", kwargs={"slug": self.organisation.slug, "project_id": self.project.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Bootcamp")

    def test_progress_is_none_when_no_activities_exist(self):
        self.assertIsNone(compute_project_progress(self.project))
        resp = self.client.get(reverse("projects:detail", kwargs={"slug": self.organisation.slug, "project_id": self.project.id}))
        self.assertContains(resp, "No activities yet.")

    def test_progress_reflects_real_activity_delivery_ratio(self):
        Activity.objects.create(programme=self.programme, project=self.project, name="A", status="delivered")
        Activity.objects.create(programme=self.programme, project=self.project, name="B", status="planned")
        self.assertEqual(compute_project_progress(self.project), 50.0)

    def test_attention_list_reflects_real_gaps(self):
        attention = compute_project_attention(self.project, self.organisation)
        texts = [item["text"] for item in attention]
        self.assertIn("Describe what this project is trying to achieve.", texts)
        self.assertIn("Assign a project manager.", texts)
        self.assertIn("Add an activity.", texts)
        self.assertIn("Set up this project's budget.", texts)

        self.project.objective = "Train 100 youth in digital skills."
        self.project.manager = self.user
        self.project.save()
        Activity.objects.create(programme=self.programme, project=self.project, name="A")
        Budget.objects.create(project=self.project, total_amount=1000)
        attention = compute_project_attention(self.project, self.organisation)
        texts = [item["text"] for item in attention]
        self.assertNotIn("Describe what this project is trying to achieve.", texts)
        self.assertNotIn("Assign a project manager.", texts)
        self.assertNotIn("Add an activity.", texts)
        self.assertNotIn("Set up this project's budget.", texts)

    def test_attention_flags_a_project_with_no_programme(self):
        orphan = Project.objects.create(organisation=self.organisation, name="Orphan Project")
        attention = compute_project_attention(orphan, self.organisation)
        texts = [item["text"] for item in attention]
        self.assertIn("Link this project to a programme.", texts)

    def test_finance_summary_separates_committed_and_actual(self):
        Budget.objects.create(project=self.project, total_amount=1000)
        Expense.objects.create(
            organisation=self.organisation, project=self.project, submitted_by=self.user,
            amount=200, description="Approved spend", status=Expense.STATUS_APPROVED,
        )
        Expense.objects.create(
            organisation=self.organisation, project=self.project, submitted_by=self.user,
            amount=150, description="Awaiting review", status=Expense.STATUS_SUBMITTED,
        )
        Expense.objects.create(
            organisation=self.organisation, project=self.project, submitted_by=self.user,
            amount=999, description="Rejected", status=Expense.STATUS_REJECTED,
        )
        summary = project_finance_summary(self.project)
        self.assertEqual(summary["planned"], 1000)
        self.assertEqual(summary["committed"], 150)
        self.assertEqual(summary["actual"], 200)
        self.assertEqual(summary["remaining"], 800)
        self.assertEqual(summary["variance"], 650)

    def test_finance_walks_through_the_dopa_bootcamp_scenario(self):
        # R20,000 budget; a R4,000 facilitator expense submitted, then
        # approved -- must never be double-counted across Committed/Actual.
        Budget.objects.create(project=self.project, total_amount=20000)
        expense = Expense.objects.create(
            organisation=self.organisation, project=self.project, submitted_by=self.user,
            amount=4000, description="Facilitator", status=Expense.STATUS_SUBMITTED,
            receipt=SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
        )
        summary = project_finance_summary(self.project)
        self.assertEqual(summary["planned"], 20000)
        self.assertEqual(summary["committed"], 4000)
        self.assertEqual(summary["actual"], 0)
        self.assertEqual(summary["remaining"], 20000)

        reviewer = User.objects.create_user(email="reviewer@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=reviewer, role=ORG_ROLE_ADMIN)
        expense.status = Expense.STATUS_APPROVED
        expense.reviewed_by = reviewer
        expense.full_clean()
        expense.save()

        summary = project_finance_summary(self.project)
        self.assertEqual(summary["planned"], 20000)
        self.assertEqual(summary["committed"], 0)  # no longer "submitted"
        self.assertEqual(summary["actual"], 4000)
        self.assertEqual(summary["remaining"], 16000)

    def test_completing_a_project_does_not_change_its_finance(self):
        Budget.objects.create(project=self.project, total_amount=20000)
        Expense.objects.create(
            organisation=self.organisation, project=self.project, submitted_by=self.user,
            amount=4000, description="Facilitator", status=Expense.STATUS_APPROVED,
        )
        self.project.status = Project.STATUS_COMPLETE
        self.project.save()
        summary = project_finance_summary(self.project)
        self.assertEqual(summary["actual"], 4000)
        self.assertEqual(summary["remaining"], 16000)  # not zeroed by completion

    def test_finance_summary_with_no_budget_yet(self):
        summary = project_finance_summary(self.project)
        self.assertFalse(summary["has_budget"])
        self.assertEqual(summary["planned"], 0)

    def test_workspace_summary_counts_match_real_data(self):
        Activity.objects.create(programme=self.programme, project=self.project, name="A")
        ProjectTask.objects.create(project=self.project, title="Book venue")
        summary = project_workspace_summary(self.project, self.organisation)
        self.assertEqual(summary["activity_count"], 1)
        self.assertEqual(summary["task_count"], 1)
        self.assertEqual(summary["evidence_count"], 0)

    def test_edit_view_updates_real_fields(self):
        url = reverse("projects:edit", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.post(url, {
            "name": "Bootcamp", "objective": "Train 100 youth.", "description": "",
            "programme": str(self.programme.id), "manager": str(self.user.id),
            "location": "Khayelitsha", "budget": "1000", "status": Project.STATUS_ACTIVE,
        })
        self.assertRedirects(resp, reverse("projects:detail", kwargs={"slug": self.organisation.slug, "project_id": self.project.id}))
        self.project.refresh_from_db()
        self.assertEqual(self.project.objective, "Train 100 youth.")
        self.assertEqual(self.project.location, "Khayelitsha")
        self.assertEqual(self.project.manager, self.user)


class ProjectActivityCreationTests(TestCase):
    """Activities are created from inside the Project and inherit its
    Programme context automatically -- never a blank, unscoped picker."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Youth Digital Literacy")
        self.project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp")

    def test_create_activity_page_prefills_project_hidden_field(self):
        url = reverse("projects:create_activity", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["form"].fields["project"].initial, self.project.id)

    def test_create_activity_saves_with_project_and_programme_inherited(self):
        url = reverse("projects:create_activity", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.post(url, {
            "name": "HTML & CSS Workshop", "status": "planned", "project": str(self.project.id),
            "expected_participants": "20", "outputs": [],
        })
        activity = Activity.objects.get(name="HTML & CSS Workshop")
        self.assertEqual(activity.programme, self.programme)
        self.assertEqual(activity.project, self.project)
        self.assertEqual(activity.expected_participants, 20)
        self.assertRedirects(resp, reverse("projects:activities", kwargs={"slug": self.organisation.slug, "project_id": self.project.id}))

    def test_cannot_create_activity_when_project_has_no_programme(self):
        orphan = Project.objects.create(organisation=self.organisation, name="Orphan Project")
        url = reverse("projects:create_activity", kwargs={"slug": self.organisation.slug, "project_id": orphan.id})
        resp = self.client.get(url, follow=True)
        self.assertRedirects(resp, reverse("projects:detail", kwargs={"slug": self.organisation.slug, "project_id": orphan.id}))
        self.assertEqual(Activity.objects.filter(project=orphan).count(), 0)

    def test_non_manager_cannot_create_activity(self):
        other = User.objects.create_user(email="member@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=other, role="fundraiser")
        self.client.force_login(other)
        url = reverse("projects:create_activity", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)


class ProjectTaskTests(TestCase):
    """Tasks are internal delivery work, belong to the Project, and may
    optionally be tied to one of the Project's own Activities."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Programme")
        self.project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp")
        self.other_project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Other")
        self.activity = Activity.objects.create(programme=self.programme, project=self.project, name="Workshop")
        self.other_activity = Activity.objects.create(programme=self.programme, project=self.other_project, name="Other Workshop")

    def test_task_activity_choices_are_scoped_to_this_project(self):
        url = reverse("projects:tasks", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.get(url)
        choices = list(resp.context["form"].fields["activity"].queryset)
        self.assertEqual(choices, [self.activity])
        self.assertNotIn(self.other_activity, choices)

    def test_create_task_links_to_activity(self):
        url = reverse("projects:tasks", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.post(url, {"title": "Book venue", "activity": str(self.activity.id), "status": "todo"})
        task = ProjectTask.objects.get(title="Book venue")
        self.assertEqual(task.project, self.project)
        self.assertEqual(task.activity, self.activity)
        self.assertRedirects(resp, url)

    def test_create_task_without_activity_is_valid(self):
        url = reverse("projects:tasks", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        self.client.post(url, {"title": "General admin", "status": "todo"})
        task = ProjectTask.objects.get(title="General admin")
        self.assertIsNone(task.activity)


class ProjectPeopleTests(TestCase):
    """People remain connected to service delivery -- reached through an
    Activity, never made children of a Task."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Programme")
        self.project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp")
        self.other_project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Other")
        self.activity = Activity.objects.create(programme=self.programme, project=self.project, name="Workshop")
        self.other_activity = Activity.objects.create(programme=self.programme, project=self.other_project, name="Other Workshop")
        self.beneficiary = Beneficiary.objects.create(
            organisation=self.organisation, programme=self.programme, first_name="Thandiwe", last_name="M",
        )

    def test_people_tab_only_shows_beneficiaries_reached_through_this_project(self):
        AttendanceRecord.objects.create(
            organisation=self.organisation, programme=self.programme, activity=self.activity,
            beneficiary=self.beneficiary, attendance_date="2026-01-10",
        )
        # A headcount entry against the *other* project's activity must not count here.
        AttendanceRecord.objects.create(
            organisation=self.organisation, programme=self.programme, activity=self.other_activity,
            headcount=5, attendance_date="2026-01-11",
        )
        resp = self.client.get(reverse("projects:people", kwargs={"slug": self.organisation.slug, "project_id": self.project.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["beneficiaries"]), [self.beneficiary])
        self.assertEqual(resp.context["people_reached"], 1)


class ProjectFormsScopingTests(TestCase):
    """ProjectForm now carries objective/location; ProjectTaskForm's
    optional activity field is always scoped to the parent Project."""

    def test_project_form_includes_objective_and_location(self):
        from apps.projects.forms import ProjectForm

        form = ProjectForm()
        self.assertIn("objective", form.fields)
        self.assertIn("location", form.fields)


class ProjectListFilterTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Programme A")
        self.project_in = Project.objects.create(organisation=self.organisation, programme=self.programme, name="In Programme")
        self.project_out = Project.objects.create(organisation=self.organisation, name="No Programme")

    def test_project_list_shows_the_parent_programme(self):
        resp = self.client.get(reverse("projects:list", kwargs={"slug": self.organisation.slug}))
        self.assertContains(resp, "Programme A")


class ProjectEvidenceTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.project = Project.objects.create(organisation=self.organisation, name="Bootcamp")

    def test_upload_evidence_attaches_to_this_project(self):
        url = reverse("projects:evidence", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.post(url, {
            "title": "Attendance register", "category": "programmes", "description": "",
            "visibility": "organisation",
            "file": SimpleUploadedFile("register.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
        })
        self.assertRedirects(resp, url)
        resp = self.client.get(url)
        self.assertContains(resp, "Attendance register")


class ModalPatternTests(TestCase):
    """Tables show data; create forms stay inside a closed modal until the
    trigger button is clicked, and re-open themselves (with entered data
    and errors intact) only when the server actually has something to
    show the user -- a failed validation."""

    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Programme")
        self.project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp")

    def test_project_list_modal_is_closed_by_default_and_opens_on_invalid_submit(self):
        url = reverse("projects:list", kwargs={"slug": self.organisation.slug})
        resp = self.client.get(url)
        self.assertContains(resp, 'data-modal-open="project-modal"')
        self.assertNotContains(resp, 'data-open-on-load="true"')

        resp = self.client.post(url, {"name": ""})  # name is required -- invalid
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-open-on-load="true"')

    def test_activities_tab_modal_closed_by_default_opens_on_error_and_preserves_entered_name(self):
        url = reverse("projects:activities", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.get(url)
        self.assertContains(resp, 'data-modal-open="activity-modal"')
        self.assertNotContains(resp, 'data-open-on-load="true"')

        resp = self.client.post(url, {"name": "", "status": "planned", "location": "A specific venue"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-open-on-load="true"')
        self.assertContains(resp, "A specific venue")  # entered data preserved in the reopened modal

    def test_tasks_tab_modal_closed_by_default_and_opens_on_error(self):
        url = reverse("projects:tasks", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.get(url)
        self.assertContains(resp, 'data-modal-open="task-modal"')
        self.assertNotContains(resp, 'data-open-on-load="true"')

        resp = self.client.post(url, {"title": "", "status": "todo"})  # title is required
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-open-on-load="true"')

    def test_budget_tab_shows_setup_trigger_then_add_line_trigger(self):
        url = reverse("projects:budget", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.get(url)
        self.assertContains(resp, 'data-modal-open="budget-modal"')
        self.assertNotContains(resp, 'data-modal-open="budget-line-modal"')

        Budget.objects.create(project=self.project, total_amount=1000)
        resp = self.client.get(url)
        self.assertContains(resp, 'data-modal-open="budget-line-modal"')
        self.assertNotContains(resp, 'data-modal-open="budget-modal"')

    def test_evidence_tab_modal_closed_by_default(self):
        url = reverse("projects:evidence", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.get(url)
        self.assertContains(resp, 'data-modal-open="evidence-modal"')
        self.assertNotContains(resp, 'data-open-on-load="true"')


class TaskCRUDTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.project = Project.objects.create(organisation=self.organisation, name="Bootcamp")
        self.task = ProjectTask.objects.create(project=self.project, title="Book venue", status="todo")

    def test_edit_task_updates_real_fields(self):
        url = reverse("projects:task_edit", kwargs={"slug": self.organisation.slug, "project_id": self.project.id, "task_id": self.task.id})
        resp = self.client.post(url, {"title": "Book bigger venue", "status": "in_progress"})
        self.assertRedirects(resp, reverse("projects:tasks", kwargs={"slug": self.organisation.slug, "project_id": self.project.id}))
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Book bigger venue")
        self.assertEqual(self.task.status, "in_progress")

    def test_delete_task_requires_post(self):
        url = reverse("projects:task_delete", kwargs={"slug": self.organisation.slug, "project_id": self.project.id, "task_id": self.task.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ProjectTask.objects.filter(id=self.task.id).exists())

        resp = self.client.post(url)
        self.assertRedirects(resp, reverse("projects:tasks", kwargs={"slug": self.organisation.slug, "project_id": self.project.id}))
        self.assertFalse(ProjectTask.objects.filter(id=self.task.id).exists())


class ProjectDeleteTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(legal_name="Org A", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN)
        self.client.force_login(self.user)
        self.programme = Programme.objects.create(organisation=self.organisation, name="Programme")
        self.project = Project.objects.create(organisation=self.organisation, programme=self.programme, name="Bootcamp")

    def test_delete_project_requires_post_and_redirects_to_programme(self):
        url = reverse("projects:delete", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Project.objects.filter(id=self.project.id).exists())

        resp = self.client.post(url)
        self.assertRedirects(resp, reverse("programmes:detail", kwargs={"slug": self.organisation.slug, "programme_id": self.programme.id}))
        self.assertFalse(Project.objects.filter(id=self.project.id).exists())

    def test_non_manager_cannot_delete_project(self):
        other = User.objects.create_user(email="member@example.com", password=PASSWORD)
        OrganisationMembership.objects.create(organisation=self.organisation, user=other, role="fundraiser")
        self.client.force_login(other)
        url = reverse("projects:delete", kwargs={"slug": self.organisation.slug, "project_id": self.project.id})
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Project.objects.filter(id=self.project.id).exists())
