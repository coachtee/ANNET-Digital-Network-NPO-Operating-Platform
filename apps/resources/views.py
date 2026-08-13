from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.resources.forms import ResourceForm
from apps.resources.models import Resource


def _require_platform_admin(request):
    # Gated on is_platform_admin only, not a dedicated "Platform Staff"
    # capability -- that tier doesn't exist yet (see
    # STAKEHOLDER_READINESS_ASSESSMENT.md §4/§7). Narrowing this to a
    # scoped "resources.manage"-style capability is future work once that
    # tier is designed, not something to improvise here.
    if not request.user.is_platform_admin:
        raise PermissionDenied


@login_required
def manage_list(request):
    _require_platform_admin(request)
    return render(request, "resources/manage_list.html", {"resources": Resource.objects.all()})


@login_required
def create(request):
    _require_platform_admin(request)
    form = ResourceForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        resource = form.save(commit=False)
        resource.created_by = request.user
        resource.save()
        messages.success(request, "Resource saved.")
        return redirect("resources:manage_list")
    return render(request, "resources/resource_form.html", {"form": form, "resource": None})


@login_required
def edit(request, resource_id):
    _require_platform_admin(request)
    resource = get_object_or_404(Resource, id=resource_id)
    form = ResourceForm(request.POST or None, request.FILES or None, instance=resource)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Resource saved.")
        return redirect("resources:manage_list")
    return render(request, "resources/resource_form.html", {"form": form, "resource": resource})
