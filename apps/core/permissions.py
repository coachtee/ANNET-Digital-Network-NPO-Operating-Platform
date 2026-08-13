"""
Capability-based authorisation framework.

Per MASTER_BUILD_SPEC section 8, permissions are designed around named
*capabilities* ("organisation.manage", "compliance.manage", ...) rather than
scattering `if role == "X"` checks through views and templates. A role is
just a named bundle of capabilities.

Two independent scopes exist:

- Organisation scope: what a user can do inside ONE organisation's
  workspace, granted via ``organisations.OrganisationMembership.role``.
- Network scope: what a user can do at the network/programme level (managing
  members, applications, network dashboards), granted via
  ``networks.NetworkStaffRole.role``.

Platform Super Administrators (``User.is_platform_admin``) implicitly hold
every capability in every scope — this is the only "escape hatch" and it is
checked explicitly, never implied by a naming convention.
"""

# --- Organisation-scoped roles -------------------------------------------

ORG_ROLE_ADMIN = "org_admin"
ORG_ROLE_EXECUTIVE_DIRECTOR = "executive_director"
ORG_ROLE_BOARD_MEMBER = "board_member"
ORG_ROLE_TREASURER = "treasurer"
ORG_ROLE_COMPLIANCE_OFFICER = "compliance_officer"
ORG_ROLE_PROJECT_MANAGER = "project_manager"
ORG_ROLE_ME_OFFICER = "me_officer"
ORG_ROLE_FINANCE_OFFICER = "finance_officer"
ORG_ROLE_STAFF = "staff"
ORG_ROLE_VOLUNTEER = "volunteer"

ORG_ROLE_CHOICES = [
    (ORG_ROLE_ADMIN, "Organisation Administrator"),
    (ORG_ROLE_EXECUTIVE_DIRECTOR, "Executive Director / CEO"),
    (ORG_ROLE_BOARD_MEMBER, "Board Member"),
    (ORG_ROLE_TREASURER, "Treasurer"),
    (ORG_ROLE_COMPLIANCE_OFFICER, "Compliance Officer"),
    (ORG_ROLE_PROJECT_MANAGER, "Project Manager"),
    (ORG_ROLE_ME_OFFICER, "M&E Officer"),
    (ORG_ROLE_FINANCE_OFFICER, "Finance Officer"),
    (ORG_ROLE_STAFF, "Staff Member"),
    (ORG_ROLE_VOLUNTEER, "Volunteer"),
]

_ALL_ORG_CAPABILITIES = {
    "organisation.view", "organisation.manage",
    "governance.view", "governance.manage",
    "policies.view", "policies.manage",
    "documents.view", "documents.manage",
    "compliance.view", "compliance.manage",
    "grants.view", "grants.manage",
    "projects.view", "projects.manage",
    "programmes.view", "programmes.manage",
    "beneficiaries.view", "beneficiaries.manage",
    "attendance.view", "attendance.manage",
    "me.view", "me.manage",
    "expenses.view", "expenses.submit", "expenses.approve",
    "reporting.view",
    "impact.view",
    "members.view", "members.manage",
}

# Each role is granted an explicit capability set — least privilege by
# default. Org Admin gets everything within the organisation.
ORG_ROLE_CAPABILITIES = {
    ORG_ROLE_ADMIN: set(_ALL_ORG_CAPABILITIES),
    ORG_ROLE_EXECUTIVE_DIRECTOR: set(_ALL_ORG_CAPABILITIES),
    ORG_ROLE_BOARD_MEMBER: {
        "organisation.view", "governance.view", "policies.view", "documents.view",
        "compliance.view", "grants.view", "projects.view", "programmes.view",
        "reporting.view", "impact.view",
    },
    ORG_ROLE_TREASURER: {
        "organisation.view", "governance.view", "governance.manage",
        "policies.view", "documents.view",
        "grants.view", "projects.view", "programmes.view",
        "expenses.view", "expenses.approve", "reporting.view", "impact.view",
    },
    ORG_ROLE_COMPLIANCE_OFFICER: {
        "organisation.view", "governance.view", "governance.manage",
        "policies.view", "policies.manage", "documents.view", "documents.manage",
        "compliance.view", "compliance.manage", "reporting.view",
    },
    ORG_ROLE_PROJECT_MANAGER: {
        "organisation.view", "documents.view", "documents.manage",
        "grants.view", "projects.view", "projects.manage",
        "programmes.view", "programmes.manage",
        "beneficiaries.view", "beneficiaries.manage",
        "attendance.view", "attendance.manage",
        "me.view", "me.manage", "expenses.view", "expenses.submit",
        "reporting.view", "impact.view",
    },
    ORG_ROLE_ME_OFFICER: {
        "organisation.view", "programmes.view", "beneficiaries.view",
        "attendance.view", "attendance.manage", "me.view", "me.manage",
        "reporting.view", "impact.view", "documents.view", "documents.manage",
    },
    ORG_ROLE_FINANCE_OFFICER: {
        "organisation.view", "grants.view", "projects.view",
        "expenses.view", "expenses.submit", "expenses.approve",
        "documents.view", "documents.manage", "reporting.view",
    },
    ORG_ROLE_STAFF: {
        "organisation.view", "programmes.view", "projects.view",
        "beneficiaries.view", "attendance.view", "attendance.manage",
        "documents.view", "expenses.view", "expenses.submit",
    },
    ORG_ROLE_VOLUNTEER: {
        "attendance.view", "attendance.manage", "expenses.submit",
    },
}

# --- Network-scoped roles (network/programme level) -----------------------

NETWORK_ROLE_ADMIN = "network_admin"
NETWORK_ROLE_MEMBERSHIP_OFFICER = "membership_officer"

NETWORK_ROLE_CHOICES = [
    (NETWORK_ROLE_ADMIN, "Network Administrator"),
    (NETWORK_ROLE_MEMBERSHIP_OFFICER, "Membership Officer"),
]

NETWORK_ROLE_CAPABILITIES = {
    NETWORK_ROLE_ADMIN: {
        "network.dashboard.view", "network.members.view", "network.members.manage",
        "network.capacity.view", "network.opportunities.manage",
        "membership.review", "membership.decide",
    },
    NETWORK_ROLE_MEMBERSHIP_OFFICER: {
        "network.dashboard.view", "network.members.view",
        "membership.review",
    },
}


def org_capabilities_for_role(role: str) -> set:
    return ORG_ROLE_CAPABILITIES.get(role, set())


def network_capabilities_for_role(role: str) -> set:
    return NETWORK_ROLE_CAPABILITIES.get(role, set())


def has_org_capability(user, organisation, capability: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_platform_admin", False):
        return True
    if organisation is None:
        return False
    membership = organisation.memberships.filter(user=user, is_active=True).first()
    if not membership:
        return False
    return capability in org_capabilities_for_role(membership.role)


def has_network_capability(user, network, capability: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_platform_admin", False):
        return True
    if network is None:
        return False
    staff_role = network.staff_roles.filter(user=user, is_active=True).first()
    if not staff_role:
        return False
    return capability in network_capabilities_for_role(staff_role.role)


# --- Platform-scoped roles (Bohlale Impact staff/admin) --------------------
#
# A third, distinct scope alongside organisation-scoped and network-scoped
# capabilities above: what a user can do in the Bohlale Impact *staff*
# portal (apps.staffadmin), which manages the platform ecosystem itself
# rather than any one organisation's workspace or any one network/
# programme. Only one real grant exists today -- User.is_platform_admin,
# checked below the same way it's the escape hatch for the other two
# scopes -- but the target role/capability shape is defined now so every
# staff-portal call site is written against has_platform_capability() from
# day one. Introducing a scoped PlatformStaffRole model later only needs
# to plug a role lookup into has_platform_capability() (mirroring exactly
# how OrganisationMembership/NetworkStaffRole are looked up above); no
# call site anywhere in apps.staffadmin would need to change.

PLATFORM_ROLE_ADMIN = "platform_admin"
PLATFORM_ROLE_CONTENT_MANAGER = "content_manager"
PLATFORM_ROLE_PROGRAMME_MANAGER = "programme_manager"
PLATFORM_ROLE_MEMBERSHIP_OFFICER = "membership_officer"
PLATFORM_ROLE_SUPPORT_OFFICER = "support_officer"
PLATFORM_ROLE_ANALYST = "analyst"

PLATFORM_ROLE_CHOICES = [
    (PLATFORM_ROLE_ADMIN, "Platform Administrator"),
    (PLATFORM_ROLE_CONTENT_MANAGER, "Content Manager"),
    (PLATFORM_ROLE_PROGRAMME_MANAGER, "Programme Manager"),
    (PLATFORM_ROLE_MEMBERSHIP_OFFICER, "Membership Officer"),
    (PLATFORM_ROLE_SUPPORT_OFFICER, "Support / Compliance Officer"),
    (PLATFORM_ROLE_ANALYST, "Analyst (Read Only)"),
]

_ALL_PLATFORM_CAPABILITIES = {
    "platform.organisations.view", "platform.organisations.manage",
    "platform.networks.view", "platform.networks.manage",
    "platform.memberships.review",
    "platform.opportunities.manage",
    "platform.resources.manage",
    "platform.events.manage",
    "platform.insights.manage",
    "platform.partnerships.manage",
    "platform.staff.manage",
    "platform.reports.view",
}

# Least-privilege target mapping for when PlatformStaffRole exists -- not
# consulted anywhere yet (has_platform_capability doesn't look roles up
# yet), kept here as the reviewable shape of what scoped staff access is
# meant to look like.
PLATFORM_ROLE_CAPABILITIES = {
    PLATFORM_ROLE_ADMIN: set(_ALL_PLATFORM_CAPABILITIES),
    PLATFORM_ROLE_CONTENT_MANAGER: {
        "platform.organisations.view", "platform.opportunities.manage", "platform.resources.manage",
        "platform.events.manage", "platform.insights.manage",
    },
    PLATFORM_ROLE_PROGRAMME_MANAGER: {
        "platform.organisations.view", "platform.networks.view", "platform.networks.manage",
        "platform.memberships.review", "platform.partnerships.manage",
    },
    PLATFORM_ROLE_MEMBERSHIP_OFFICER: {
        "platform.organisations.view", "platform.networks.view", "platform.memberships.review",
    },
    PLATFORM_ROLE_SUPPORT_OFFICER: {
        "platform.organisations.view", "platform.reports.view",
    },
    PLATFORM_ROLE_ANALYST: {
        "platform.organisations.view", "platform.networks.view", "platform.reports.view",
    },
}


def platform_capabilities_for_role(role: str) -> set:
    return PLATFORM_ROLE_CAPABILITIES.get(role, set())


def has_platform_capability(user, capability: str) -> bool:
    """Every apps.staffadmin view should gate on this, never on
    is_platform_admin directly -- that keeps them all forward-compatible
    with scoped staff roles without a rewrite. Today it's equivalent to
    is_platform_admin because that's the only real grant; the capability
    argument is accepted (and required at call sites) precisely so it's
    already meaningful once PLATFORM_ROLE_CAPABILITIES is wired to a real
    role lookup here.
    """
    if not user or not user.is_authenticated:
        return False
    return bool(getattr(user, "is_platform_admin", False))
