from django import forms

from apps.programmes.models import Activity, Programme


def _to_list(value):
    return [v.strip() for v in value.split(",") if v.strip()]


class ProgrammeWizardDetailsForm(forms.ModelForm):
    """Wizard step 1: Programme. Also used as the plain create form."""

    class Meta:
        model = Programme
        fields = ["name", "programme_area", "status", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class ProgrammeWizardWhyForm(forms.ModelForm):
    """Wizard step 2: Why. "What problem are you trying to address?" /
    "What do you want to achieve?" -- reuses the existing
    theory_of_change_summary field for the latter rather than adding a
    duplicate concept."""

    class Meta:
        model = Programme
        fields = ["need_and_background", "theory_of_change_summary"]
        labels = {
            "need_and_background": "What problem are you trying to address?",
            "theory_of_change_summary": "What do you want to achieve?",
        }
        widgets = {
            "need_and_background": forms.Textarea(attrs={"rows": 4}),
            "theory_of_change_summary": forms.Textarea(attrs={"rows": 3}),
        }


class ProgrammeWizardWhoWhereForm(forms.Form):
    """Wizard step 3: Who & Where. target_beneficiary_groups/locations are
    already-existing JSONField(list) columns on Programme with no form
    ever exposing them -- same comma-separated-text pattern already used
    for Organisation.sectors/programme_areas in the onboarding wizard."""

    target_beneficiary_groups = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        label="Who will benefit?", help_text="Comma-separated, e.g. Youth aged 18-35, Unemployed graduates",
    )
    locations = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        label="Where will this take place?", help_text="Comma-separated, e.g. Khayelitsha, Ekurhuleni",
    )

    def save(self, programme):
        programme.target_beneficiary_groups = _to_list(self.cleaned_data["target_beneficiary_groups"])
        programme.locations = _to_list(self.cleaned_data["locations"])
        programme.save(update_fields=["target_beneficiary_groups", "locations"])


class ProgrammeWizardPeopleResourcesForm(forms.ModelForm):
    """Wizard step 6: People & Resources. Deliberately a single narrative
    field, not a staff roster -- see the architecture proposal's flagged
    DSD C4 gap."""

    class Meta:
        model = Programme
        fields = ["staffing_plan"]
        labels = {"staffing_plan": "Who will deliver this programme, and what resources do they need?"}
        widgets = {"staffing_plan": forms.Textarea(attrs={"rows": 4})}


class ProgrammeWizardFundingForm(forms.ModelForm):
    """Wizard step 7: Budget & Funding. Project-level budgets are already
    captured in step 5 (Projects & Activities); this step is specifically
    about funding sources."""

    class Meta:
        model = Programme
        fields = ["grants"]
        labels = {"grants": "Which funding sources support this programme?"}

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["grants"].queryset = organisation.grants.all()


class ProgrammePlanForm(forms.ModelForm):
    """Plan tab edit form -- the same fields the wizard collects, editable
    afterwards in one place rather than only during initial setup."""

    target_beneficiary_groups = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), help_text="Comma-separated",
    )
    locations = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), help_text="Comma-separated",
    )

    class Meta:
        model = Programme
        fields = [
            "need_and_background", "theory_of_change_summary", "start_date", "end_date",
            "staffing_plan",
        ]
        widgets = {
            "need_and_background": forms.Textarea(attrs={"rows": 4}),
            "theory_of_change_summary": forms.Textarea(attrs={"rows": 3}),
            "staffing_plan": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["target_beneficiary_groups"].initial = ", ".join(self.instance.target_beneficiary_groups)
            self.fields["locations"].initial = ", ".join(self.instance.locations)

    def save(self, commit=True):
        programme = super().save(commit=False)
        programme.target_beneficiary_groups = _to_list(self.cleaned_data["target_beneficiary_groups"])
        programme.locations = _to_list(self.cleaned_data["locations"])
        if commit:
            programme.save()
        return programme


class ProgrammeForm(forms.ModelForm):
    """Legacy full-form edit, kept for any direct Programme edit outside
    the wizard/Plan-tab split."""

    sectors_help = "Comma-separated"

    class Meta:
        model = Programme
        fields = ["name", "description", "programme_area", "theory_of_change_summary", "status", "grants"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "theory_of_change_summary": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["grants"].queryset = organisation.grants.all()


class ActivityForm(forms.ModelForm):
    """Reused for both the wizard's Activities step and the dedicated
    "New Activity" page. Every relational field here is progressively
    scoped/pre-filled from the parent Programme/Project rather than shown
    as an open-ended picker -- see the architecture proposal's "progressive
    context inheritance" section.
    """

    class Meta:
        model = Activity
        fields = [
            "name", "scheduled_date", "location", "expected_participants", "status",
            "project", "outputs", "responsible_person", "budget_line",
        ]
        widgets = {"scheduled_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, programme=None, project=None, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if programme is not None:
            self.fields["project"].queryset = programme.projects.all()
            self.fields["outputs"].queryset = programme.outputs.all()
        if organisation is not None:
            self.fields["responsible_person"].queryset = self.fields["responsible_person"].queryset.filter(
                organisation_memberships__organisation=organisation, organisation_memberships__is_active=True
            ).distinct()
        if project is not None:
            self.fields["project"].initial = project.id
            self.fields["project"].widget = forms.HiddenInput()
            if project.manager_id:
                self.fields["responsible_person"].initial = project.manager_id
            self.fields["budget_line"].queryset = _budget_lines_for_project(project)
        else:
            self.fields["budget_line"].queryset = self.fields["budget_line"].queryset.none()


def _budget_lines_for_project(project):
    from apps.expenses.models import BudgetLine

    return BudgetLine.objects.filter(budget__project=project)
