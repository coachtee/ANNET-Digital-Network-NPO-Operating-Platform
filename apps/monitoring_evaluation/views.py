from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import has_org_capability
from apps.monitoring_evaluation.forms import IndicatorForm, IndicatorPeriodValueForm, OutcomeForm, OutputForm
from apps.monitoring_evaluation.models import Indicator
from apps.monitoring_evaluation.services import attendance_count_for_period
from apps.organisations.services import get_organisation_or_404_for_user
from apps.programmes.models import Programme


@login_required
def me_dashboard(request, slug):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    if not has_org_capability(request.user, organisation, "me.view"):
        raise PermissionDenied
    programmes = organisation.programmes.prefetch_related("indicators")
    return render(request, "monitoring_evaluation/dashboard.html", {"organisation": organisation, "programmes": programmes})


@login_required
def programme_me(request, slug, programme_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    programme = get_object_or_404(Programme, id=programme_id, organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "me.manage")

    # Distinct auto_id per form -- all three render "title"/"outcome"
    # fields, and without this every one would emit the same id_title/
    # id_outcome DOM ids, so a <label for="id_title"> in the Output or
    # Indicator card would focus the Outcome card's field instead.
    outcome_form = OutcomeForm(auto_id="id_outcome_%s")
    output_form = OutputForm(programme=programme, auto_id="id_output_%s")
    indicator_form = IndicatorForm(programme=programme, auto_id="id_indicator_%s")
    if request.method == "POST" and can_manage:
        if "add_outcome" in request.POST:
            outcome_form = OutcomeForm(request.POST, auto_id="id_outcome_%s")
            if outcome_form.is_valid():
                outcome = outcome_form.save(commit=False)
                outcome.programme = programme
                outcome.save()
                return redirect("monitoring_evaluation:programme_me", slug=slug, programme_id=programme.id)
        elif "add_output" in request.POST:
            output_form = OutputForm(request.POST, programme=programme, auto_id="id_output_%s")
            if output_form.is_valid():
                output = output_form.save(commit=False)
                output.programme = programme
                output.save()
                return redirect("monitoring_evaluation:programme_me", slug=slug, programme_id=programme.id)
        elif "add_indicator" in request.POST:
            indicator_form = IndicatorForm(request.POST, programme=programme, auto_id="id_indicator_%s")
            if indicator_form.is_valid():
                indicator = indicator_form.save(commit=False)
                indicator.programme = programme
                indicator.save()
                return redirect("monitoring_evaluation:programme_me", slug=slug, programme_id=programme.id)

    context = {
        "organisation": organisation, "programme": programme, "can_manage": can_manage,
        "outcomes": programme.outcomes.all(), "outputs": programme.outputs.all(), "indicators": programme.indicators.all(),
        "outcome_form": outcome_form, "output_form": output_form, "indicator_form": indicator_form,
    }
    return render(request, "monitoring_evaluation/programme_me.html", context)


@login_required
def indicator_detail(request, slug, indicator_id):
    organisation = get_organisation_or_404_for_user(request.user, slug)
    indicator = get_object_or_404(Indicator, id=indicator_id, programme__organisation=organisation)
    can_manage = has_org_capability(request.user, organisation, "me.manage")
    form = IndicatorPeriodValueForm()

    if request.method == "POST" and can_manage:
        form = IndicatorPeriodValueForm(request.POST)
        if form.is_valid():
            period_value = form.save(commit=False)
            if indicator.auto_from_attendance:
                period_value.actual_value = attendance_count_for_period(
                    indicator.programme, period_value.period_start, period_value.period_end
                )
                period_value.means_of_verification = period_value.means_of_verification or "Attendance records"
            period_value.indicator = indicator
            period_value.save()
            messages.success(request, "Actual value recorded.")
            return redirect("monitoring_evaluation:indicator_detail", slug=slug, indicator_id=indicator.id)

    context = {
        "organisation": organisation, "indicator": indicator, "can_manage": can_manage,
        "form": form, "period_values": indicator.period_values.all(),
    }
    return render(request, "monitoring_evaluation/indicator_detail.html", context)
