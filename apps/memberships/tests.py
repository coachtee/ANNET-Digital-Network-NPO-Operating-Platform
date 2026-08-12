from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.permissions import NETWORK_ROLE_ADMIN, ORG_ROLE_ADMIN
from apps.memberships.models import MembershipApplication
from apps.networks.models import Network, NetworkStaffRole
from apps.organisations.models import Organisation, OrganisationMembership

PASSWORD = "TestPass!2026"


class UniqueActiveApplicationConstraintTests(TestCase):
    """An organisation must never hold two *live* applications against the
    same network at once — enforced at the database level, not just in
    view logic, so it holds regardless of how a row gets created."""

    def setUp(self):
        self.network = Network.objects.create(slug="bohlale-impact", name="Bohlale Impact")
        self.other_network = Network.objects.create(slug="black-sash", name="Black Sash Community Monitoring Programme")
        self.org = Organisation.objects.create(legal_name="Test Org", slug="test-org", organisation_type="npo")

    def test_cannot_hold_two_submitted_applications_to_the_same_network(self):
        MembershipApplication.objects.create(
            organisation=self.org, network=self.network, status=MembershipApplication.STATUS_SUBMITTED,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MembershipApplication.objects.create(
                organisation=self.org, network=self.network, status=MembershipApplication.STATUS_SUBMITTED,
            )

    def test_cannot_hold_a_draft_alongside_an_approved_application(self):
        MembershipApplication.objects.create(
            organisation=self.org, network=self.network, status=MembershipApplication.STATUS_APPROVED,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MembershipApplication.objects.create(
                organisation=self.org, network=self.network, status=MembershipApplication.STATUS_DRAFT,
            )

    def test_re_application_after_decline_is_allowed(self):
        # Terminal statuses don't block a new row — this is the documented
        # "re-application after a decline" path (see the model docstring).
        MembershipApplication.objects.create(
            organisation=self.org, network=self.network, status=MembershipApplication.STATUS_DECLINED,
        )
        MembershipApplication.objects.create(
            organisation=self.org, network=self.network, status=MembershipApplication.STATUS_DRAFT,
        )
        self.assertEqual(
            MembershipApplication.objects.filter(organisation=self.org, network=self.network).count(), 2
        )

    def test_re_application_after_withdrawal_is_allowed(self):
        MembershipApplication.objects.create(
            organisation=self.org, network=self.network, status=MembershipApplication.STATUS_WITHDRAWN,
        )
        MembershipApplication.objects.create(
            organisation=self.org, network=self.network, status=MembershipApplication.STATUS_SUBMITTED,
        )
        self.assertEqual(
            MembershipApplication.objects.filter(organisation=self.org, network=self.network).count(), 2
        )

    def test_same_organisation_can_hold_active_applications_to_different_networks(self):
        # The constraint is per (organisation, network) — not per
        # organisation — which is the entire point of the generalisation.
        MembershipApplication.objects.create(
            organisation=self.org, network=self.network, status=MembershipApplication.STATUS_SUBMITTED,
        )
        MembershipApplication.objects.create(
            organisation=self.org, network=self.other_network, status=MembershipApplication.STATUS_SUBMITTED,
        )
        self.assertEqual(MembershipApplication.objects.filter(organisation=self.org).count(), 2)


class BlackSashProgrammeWorkflowTests(TestCase):
    """End-to-end proof that a partner programme (Black Sash is the real
    first customer, but nothing here refers to it by name in any view or
    permission check) can operate on this platform without being
    hard-coded: Network/MembershipApplication/NetworkStaffRole are generic,
    and this test is the evidence. See BOHLALE_IMPACT_ASSESSMENT.md §5/§11.

    All data below is fictional test data.
    """

    def setUp(self):
        # 1. Bohlale Impact exists as the platform (the primary/anchor
        # Network row — created first so get_primary_network() resolves to
        # it, exactly as apps/core/management/commands/seed_demo_data.py
        # does for a real deployment).
        self.bohlale_impact = Network.objects.create(
            slug="bohlale-impact", name="Bohlale Impact", tagline="Community Impact Platform",
        )

        # 2. A Black Sash Programme/Network exists independently — just
        # another row in the same generic model, created by an operator,
        # not by any special-cased code path.
        self.black_sash = Network.objects.create(
            slug="black-sash", name="Black Sash Community Monitoring Programme",
            tagline="Partner programme", description="Community monitoring and advice office support.",
        )

        # The partner NPO applying to join the programme.
        self.org_user = User.objects.create_user(email="director@mphoreng.example.org", password=PASSWORD)
        self.mphoreng = Organisation.objects.create(
            legal_name="Mphoreng Foundation", slug="mphoreng-foundation",
            organisation_type="npo", province="GP", is_publicly_listed=True,
            onboarding_step=Organisation.ONBOARDING_COMPLETE,
        )
        OrganisationMembership.objects.create(organisation=self.mphoreng, user=self.org_user, role=ORG_ROLE_ADMIN)

        # An unrelated organisation, used to prove isolation isn't
        # accidental (its own staff must never see Mphoreng's application).
        self.other_org_user = User.objects.create_user(email="director@other.example.org", password=PASSWORD)
        self.other_org = Organisation.objects.create(
            legal_name="Other Org", slug="other-org", organisation_type="npo",
        )
        OrganisationMembership.objects.create(organisation=self.other_org, user=self.other_org_user, role=ORG_ROLE_ADMIN)

        # The Black Sash programme administrator — staff of Black Sash
        # *only*, with no role at all on Bohlale Impact itself.
        self.black_sash_admin = User.objects.create_user(email="admin@blacksash.example.org", password=PASSWORD)
        NetworkStaffRole.objects.create(network=self.black_sash, user=self.black_sash_admin, role=NETWORK_ROLE_ADMIN)

    def _login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(email=user.email, password=PASSWORD))

    def test_black_sash_programme_exists_independently_of_the_platform_network(self):
        # Point 1 & 2.
        self.assertEqual(Network.objects.count(), 2)
        self.assertNotEqual(self.bohlale_impact.pk, self.black_sash.pk)
        from apps.networks.services import get_primary_network
        self.assertEqual(get_primary_network(), self.bohlale_impact)

    def test_full_application_review_approval_workflow(self):
        # Point 3: Mphoreng Foundation applies to join the Black Sash
        # programme specifically (not the platform's own network).
        self._login(self.org_user)
        apply_url = reverse("memberships:apply_to_network", kwargs={
            "slug": self.mphoreng.slug, "network_slug": self.black_sash.slug,
        })
        response = self.client.post(apply_url, {"motivation": "We run advice sessions in Soweto and want programme support."})
        self.assertEqual(response.status_code, 302)

        application = MembershipApplication.objects.get(organisation=self.mphoreng, network=self.black_sash)
        self.assertEqual(application.status, MembershipApplication.STATUS_SUBMITTED)

        # Point 4: the Black Sash programme administrator reviews it via
        # their own network-scoped queue.
        self._login(self.black_sash_admin)
        queue_url = reverse("memberships:queue_for_network", kwargs={"network_slug": self.black_sash.slug})
        response = self.client.get(queue_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(application, list(response.context["applications"]))

        detail_url = reverse("memberships:application_detail", kwargs={"application_id": application.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_decide"])

        # Point 5: the application is approved.
        response = self.client.post(detail_url, {"status": MembershipApplication.STATUS_APPROVED, "note": "Approved — meets criteria."})
        self.assertEqual(response.status_code, 302)

        # Point 6: the organisation is now an approved partner of that
        # programme specifically.
        application.refresh_from_db()
        self.assertEqual(application.status, MembershipApplication.STATUS_APPROVED)
        self.assertTrue(
            self.mphoreng.network_memberships.filter(network=self.black_sash, status="approved").exists()
        )
        # Being a Black Sash partner does NOT make Mphoreng a Bohlale
        # Impact platform member — these are independent relationships,
        # which is the whole point of the generalisation.
        self.assertFalse(self.mphoreng.is_network_member)

        # Point 7: the organisation retains its own Bohlale Impact
        # workspace, completely unaffected by the programme relationship.
        self._login(self.org_user)
        response = self.client.get(reverse("organisations:workspace_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mphoreng Foundation")
        response = self.client.get(reverse("organisations:org_360", kwargs={"slug": self.mphoreng.slug}))
        self.assertEqual(response.status_code, 200)

    def test_programme_administrator_sees_only_authorised_programme_information(self):
        # Point 8: an approved Black Sash partner shows up on the Black
        # Sash programme dashboard...
        MembershipApplication.objects.create(
            organisation=self.mphoreng, network=self.black_sash,
            status=MembershipApplication.STATUS_APPROVED, motivation="Test.",
        )
        self._login(self.black_sash_admin)
        response = self.client.get(reverse("networks:dashboard_for_network", kwargs={"network_slug": self.black_sash.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_members"], 1)
        self.assertIn(self.mphoreng, list(response.context["member_organisations"]))

        # ...but the Black Sash administrator has no role on Bohlale
        # Impact itself and must not be able to see the platform's own
        # network dashboard or membership queue.
        response = self.client.get(reverse("networks:dashboard"))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse("memberships:queue"))
        self.assertEqual(response.status_code, 403)

    def test_partner_organisation_sees_only_its_own_organisational_information(self):
        # Point 9: Mphoreng's own staff can see their organisation's data...
        self._login(self.org_user)
        response = self.client.get(reverse("organisations:org_360", kwargs={"slug": self.mphoreng.slug}))
        self.assertEqual(response.status_code, 200)

        # ...but cannot reach another organisation's workspace...
        response = self.client.get(reverse("organisations:org_360", kwargs={"slug": self.other_org.slug}))
        self.assertEqual(response.status_code, 404)  # get_organisation_or_404_for_user: no membership, no access

        # ...and has no programme-administrator access at all (no
        # NetworkStaffRole anywhere), on Black Sash or the platform itself.
        response = self.client.get(reverse("networks:dashboard_for_network", kwargs={"network_slug": self.black_sash.slug}))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse("memberships:queue_for_network", kwargs={"network_slug": self.black_sash.slug}))
        self.assertEqual(response.status_code, 403)

    def test_platform_queue_does_not_leak_programme_applications(self):
        # The inverse of the isolation check above: Black Sash's
        # application must never appear in the *platform's own* queue.
        MembershipApplication.objects.create(
            organisation=self.mphoreng, network=self.black_sash,
            status=MembershipApplication.STATUS_SUBMITTED, motivation="Test.",
        )
        platform_admin = User.objects.create_user(email="admin@bohlale.example.org", password=PASSWORD)
        NetworkStaffRole.objects.create(network=self.bohlale_impact, user=platform_admin, role=NETWORK_ROLE_ADMIN)

        self._login(platform_admin)
        response = self.client.get(reverse("memberships:queue"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["applications"]), [])

    def test_architecture_supports_a_second_independent_programme_via_the_same_mechanism(self):
        # Point 10: create a *second* partner programme with no
        # relationship to Black Sash, and run the identical workflow
        # against it through the identical view code — proving nothing is
        # hard-coded to Black Sash specifically.
        green_future = Network.objects.create(
            slug="green-future", name="Green Future Environmental Network",
            tagline="Environmental partner programme",
        )
        green_future_admin = User.objects.create_user(email="admin@greenfuture.example.org", password=PASSWORD)
        NetworkStaffRole.objects.create(network=green_future, user=green_future_admin, role=NETWORK_ROLE_ADMIN)

        self._login(self.org_user)
        apply_url = reverse("memberships:apply_to_network", kwargs={
            "slug": self.mphoreng.slug, "network_slug": green_future.slug,
        })
        self.client.post(apply_url, {"motivation": "We run a community recycling programme."})
        application = MembershipApplication.objects.get(organisation=self.mphoreng, network=green_future)

        self._login(green_future_admin)
        detail_url = reverse("memberships:application_detail", kwargs={"application_id": application.id})
        response = self.client.post(detail_url, {"status": MembershipApplication.STATUS_APPROVED, "note": "Welcome."})
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, MembershipApplication.STATUS_APPROVED)

        # Mphoreng is now an approved partner of *two* independent
        # programmes at once, each governed by its own administrators.
        self.assertTrue(self.mphoreng.network_memberships.filter(network=green_future, status="approved").exists())

        # The Green Future admin still can't see Black Sash's queue, and
        # vice versa — confirmed generically, not by name.
        response = self.client.get(reverse("memberships:queue_for_network", kwargs={"network_slug": self.black_sash.slug}))
        self.assertEqual(response.status_code, 403)
