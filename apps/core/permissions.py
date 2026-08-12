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
