from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.core.utils import ensure_hosts_present


class EnsureSuperuserCommandTests(TestCase):
    """The docker entrypoint calls this on every container startup, so it
    must be safe to run repeatedly without resetting an existing admin's
    password."""

    @override_settings()
    def test_creates_superuser_when_missing(self, *_):
        import os
        os.environ["DJANGO_SUPERUSER_EMAIL"] = "admin@example.com"
        os.environ["DJANGO_SUPERUSER_PASSWORD"] = "InitialGeneratedPass!23"
        try:
            call_command("ensure_superuser")
        finally:
            del os.environ["DJANGO_SUPERUSER_EMAIL"]
            del os.environ["DJANGO_SUPERUSER_PASSWORD"]

        user = User.objects.get(email="admin@example.com")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_platform_admin)
        self.assertTrue(user.check_password("InitialGeneratedPass!23"))

    def test_does_not_reset_password_on_rerun(self):
        import os
        user = User.objects.create_user(email="admin2@example.com", password="OriginalPass!23")
        user.is_superuser = True
        user.is_staff = True
        user.save()

        os.environ["DJANGO_SUPERUSER_EMAIL"] = "admin2@example.com"
        os.environ["DJANGO_SUPERUSER_PASSWORD"] = "SomeNewPassAttempt!23"
        try:
            call_command("ensure_superuser")
        finally:
            del os.environ["DJANGO_SUPERUSER_EMAIL"]
            del os.environ["DJANGO_SUPERUSER_PASSWORD"]

        user.refresh_from_db()
        self.assertTrue(user.check_password("OriginalPass!23"))
        self.assertFalse(user.check_password("SomeNewPassAttempt!23"))


class EnsureHostsPresentTests(TestCase):
    def test_appends_missing_hosts_without_duplicating(self):
        self.assertEqual(
            ensure_hosts_present(["impact.bohlale.co.za"], "127.0.0.1", "localhost"),
            ["impact.bohlale.co.za", "127.0.0.1", "localhost"],
        )

    def test_does_not_duplicate_hosts_already_present(self):
        self.assertEqual(
            ensure_hosts_present(["127.0.0.1", "localhost"], "127.0.0.1", "localhost"),
            ["127.0.0.1", "localhost"],
        )

    def test_does_not_mutate_input_list(self):
        original = ["impact.bohlale.co.za"]
        ensure_hosts_present(original, "127.0.0.1")
        self.assertEqual(original, ["impact.bohlale.co.za"])


class HealthCheckViewTests(TestCase):
    """GET /health/ is the Docker/Kubernetes/Coolify liveness and readiness
    probe — it must require no auth, touch no database, and never redirect,
    since probes hit the container directly over plain HTTP and don't follow
    redirects."""

    def test_returns_200_ok_with_plain_text_body(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_requires_no_authentication(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

    def test_does_not_query_the_database(self):
        with self.assertNumQueries(0):
            self.client.get("/health/")

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_never_redirects_even_when_ssl_redirect_is_enabled(self):
        response = self.client.get("/health/", secure=False)
        self.assertEqual(response.status_code, 200)


class FormLayoutStandardTests(TestCase):
    """The application-wide two-column modal/form standard.

    The rule lives in partials/_form_fields.html + .form-grid, so these
    tests pin the shared mechanism rather than re-checking every screen.
    """

    def setUp(self):
        from apps.accounts.models import User
        from apps.core.permissions import ORG_ROLE_ADMIN
        from apps.organisations.models import Organisation, OrganisationMembership

        self.organisation = Organisation.objects.create(legal_name="DOPA", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password="TestPass!2026")
        OrganisationMembership.objects.create(
            organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN,
        )
        self.client.force_login(self.user)

    def test_split_names_filter(self):
        from apps.core.templatetags.text_filters import split_names

        self.assertEqual(split_names("a,b , c"), ["a", "b", "c"])
        self.assertEqual(split_names(""), [])
        self.assertEqual(split_names(None), [])

    def test_form_fields_partial_renders_the_two_column_grid(self):
        from django.template import Context, Template

        from apps.projects.forms import ProjectForm

        html = Template(
            '{% include "partials/_form_fields.html" %}'
        ).render(Context({"form": ProjectForm(organisation=self.organisation)}))
        self.assertIn('class="form-grid"', html)
        self.assertNotIn("form-group-wide", html)

    def test_wide_fields_span_both_columns(self):
        from django.template import Context, Template

        from apps.projects.forms import ProjectForm

        html = Template(
            '{% include "partials/_form_fields.html" with wide_fields="description" %}'
        ).render(Context({"form": ProjectForm(organisation=self.organisation)}))
        self.assertIn("form-group-wide", html)
        # Exactly the declared field is wide, not every field.
        self.assertEqual(html.count("form-group-wide"), 1)

    def test_columns_1_forces_a_single_column(self):
        from django.template import Context, Template

        from apps.monitoring_evaluation.forms import OutcomeForm

        html = Template(
            '{% include "partials/_form_fields.html" with columns=1 %}'
        ).render(Context({"form": OutcomeForm()}))
        self.assertIn('class="form-single"', html)
        self.assertNotIn('class="form-grid"', html)

    def test_readiness_gate_error_stays_visible_in_the_two_column_layout(self):
        from django.template import Context, Template

        from apps.programmes.models import Programme
        from apps.projects.forms import ProjectForm
        from apps.projects.models import Project

        programme = Programme.objects.create(organisation=self.organisation, name="Unready")
        form = ProjectForm(
            {"name": "Bootcamp", "programme": str(programme.id), "status": Project.STATUS_ACTIVE, "budget": "0"},
            organisation=self.organisation,
        )
        self.assertFalse(form.is_valid())
        html = Template('{% include "partials/_form_fields.html" %}').render(Context({"form": form}))
        # Raised in clean_programme(), so Django attaches it to that field --
        # it renders beside the Programme selector, not as a banner.
        self.assertIn("Complete the Programme Plan first", html)
        self.assertIn("field-error", html)

    def test_non_field_errors_render_above_the_grid(self):
        from django import forms as djforms
        from django.template import Context, Template

        class FormWithFormError(djforms.Form):
            first = djforms.CharField(required=False)
            second = djforms.CharField(required=False)

            def clean(self):
                raise djforms.ValidationError("Whole-form problem.")

        form = FormWithFormError({})
        self.assertFalse(form.is_valid())
        html = Template('{% include "partials/_form_fields.html" %}').render(Context({"form": form}))
        self.assertIn("Whole-form problem.", html)
        self.assertLess(html.index("Whole-form problem."), html.index('class="form-grid"'))

    def test_project_form_field_order_pairs_columns_sensibly(self):
        from apps.projects.forms import ProjectForm

        order = list(ProjectForm(organisation=self.organisation).fields)
        self.assertEqual(order[:4], ["name", "objective", "programme", "grant"])
        self.assertEqual(order[-1], "description")  # spans both columns, sits last

    def test_no_project_fields_were_dropped_in_the_layout_refactor(self):
        from apps.projects.forms import ProjectForm

        self.assertEqual(
            set(ProjectForm(organisation=self.organisation).fields),
            {"name", "objective", "description", "grant", "programme", "manager",
             "location", "start_date", "end_date", "budget", "status"},
        )

    def test_add_person_opens_as_a_modal_on_the_people_list(self):
        resp = self.client.get(reverse("beneficiaries:list", kwargs={"slug": self.organisation.slug}))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('data-modal-open="beneficiary-modal"', html)
        self.assertIn('id="beneficiary-modal"', html)

    def test_add_person_submits_from_the_modal(self):
        from apps.beneficiaries.models import Beneficiary
        from apps.programmes.models import Programme

        programme = Programme.objects.create(organisation=self.organisation, name="Youth Digital Skills")
        resp = self.client.post(reverse("beneficiaries:list", kwargs={"slug": self.organisation.slug}), {
            "programme": str(programme.id), "mode": "named",
            "first_name": "Nomsa", "last_name": "Dlamini",
        })
        self.assertRedirects(resp, reverse("beneficiaries:list", kwargs={"slug": self.organisation.slug}))
        self.assertTrue(Beneficiary.objects.filter(first_name="Nomsa", organisation=self.organisation).exists())

    def test_invalid_modal_submission_reopens_the_modal_with_errors(self):
        resp = self.client.post(reverse("beneficiaries:list", kwargs={"slug": self.organisation.slug}), {
            "programme": "", "mode": "", "first_name": "", "last_name": "",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('data-open-on-load="true"', resp.content.decode())


class TemplateChromeIntegrityTests(TestCase):
    """Regression: a two-line ``{# ... #}`` comment in workspace_base.html
    leaked into the rendered HTML as literal text. It contained an
    ``<a href>``, which the browser parsed as an unclosed anchor wrapping
    the whole .app-content -- so every modal trigger on every workspace
    page navigated instead of opening. Django's ``{# #}`` is single-line
    only; multi-line comments need ``{% comment %}``.
    """

    def setUp(self):
        from apps.accounts.models import User
        from apps.core.permissions import ORG_ROLE_ADMIN
        from apps.organisations.models import Organisation, OrganisationMembership

        self.organisation = Organisation.objects.create(legal_name="DOPA", organisation_type="npo")
        self.user = User.objects.create_user(email="admin@example.com", password="TestPass!2026")
        OrganisationMembership.objects.create(
            organisation=self.organisation, user=self.user, role=ORG_ROLE_ADMIN,
        )
        self.client.force_login(self.user)

    def _workspace_pages(self):
        return [
            reverse("programmes:list", kwargs={"slug": self.organisation.slug}),
            reverse("projects:list", kwargs={"slug": self.organisation.slug}),
            reverse("beneficiaries:list", kwargs={"slug": self.organisation.slug}),
        ]

    def test_no_unrendered_template_syntax_leaks_into_workspace_pages(self):
        for url in self._workspace_pages():
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn("{#", html)
                self.assertNotIn("{%", html)
                self.assertNotIn("{{", html)

    def test_modal_triggers_are_not_swallowed_by_a_stray_anchor(self):
        """The content area must not sit inside an <a>, or clicking a
        modal trigger navigates instead of opening the modal."""
        import re

        for url in self._workspace_pages():
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                before_content = html.split('<div class="app-content">')[0]
                opened = len(re.findall(r"<a\b", before_content))
                closed = len(re.findall(r"</a\s*>", before_content))
                self.assertEqual(
                    opened, closed,
                    f"{opened - closed} unclosed <a> before .app-content -- it would wrap the page content.",
                )
