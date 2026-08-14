from django import forms

from apps.organisations.models import PROVINCE_CHOICES
from apps.programmes.models import (
    Activity,
    Assumption,
    ContextNote,
    LearningLogEntry,
    LearningQuestion,
    Programme,
    ProgrammeMembership,
)


def _to_list(value):
    return [v.strip() for v in value.split(",") if v.strip()]


class ProgrammeMembershipForm(forms.ModelForm):
    """Assign an existing organisation member to the Programme Team --
    never creates a new person, only references one. Scoped to active
    members of the organisation so this can never reach outside it."""

    class Meta:
        model = ProgrammeMembership
        fields = ["user", "role", "start_date", "end_date", "responsibilities", "status"]
        labels = {"user": "Person"}
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "responsibilities": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, organisation=None, programme=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["user"].queryset = self.fields["user"].queryset.filter(
                organisation_memberships__organisation=organisation, organisation_memberships__is_active=True
            ).distinct()
        if programme is not None:
            self.fields["user"].queryset = self.fields["user"].queryset.exclude(
                programme_memberships__programme=programme, programme_memberships__status=ProgrammeMembership.STATUS_ACTIVE,
            )


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
    province = forms.ChoiceField(
        required=False, choices=[("", "---------")] + PROVINCE_CHOICES, label="Primary province",
    )
    locations = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        label="Where, more specifically?", help_text="District/municipality/locality/venue, comma-separated, e.g. Khayelitsha, Ekurhuleni",
    )

    def save(self, programme):
        programme.target_beneficiary_groups = _to_list(self.cleaned_data["target_beneficiary_groups"])
        programme.province = self.cleaned_data["province"]
        programme.locations = _to_list(self.cleaned_data["locations"])
        programme.save(update_fields=["target_beneficiary_groups", "province", "locations"])


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
            "need_and_background", "theory_of_change_summary", "programme_area", "province",
            "start_date", "end_date", "staffing_plan",
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


class TheoryOfChangeForm(forms.ModelForm):
    """"If we do X, we expect Y to happen because Z" -- deliberately just
    three plain-language fields, no diagram editor."""

    class Meta:
        model = Programme
        fields = ["toc_what", "toc_change", "toc_why"]
        labels = {
            "toc_what": "What are we doing?",
            "toc_change": "What change do we expect?",
            "toc_why": "Why do we believe this will contribute to that change?",
        }
        widgets = {
            "toc_what": forms.Textarea(attrs={"rows": 2}),
            "toc_change": forms.Textarea(attrs={"rows": 2}),
            "toc_why": forms.Textarea(attrs={"rows": 2}),
        }


class AssumptionForm(forms.ModelForm):
    class Meta:
        model = Assumption
        fields = ["statement", "importance", "status", "note"]
        labels = {"statement": "What needs to be true for this approach to work?"}
        widgets = {
            "statement": forms.Textarea(attrs={"rows": 2}),
            "note": forms.Textarea(attrs={"rows": 2}),
        }


class LearningQuestionForm(forms.ModelForm):
    class Meta:
        model = LearningQuestion
        fields = ["question", "why_it_matters", "status", "answer_note"]
        labels = {
            "question": "What do you need to learn while the programme is running?",
            "why_it_matters": "Why does this matter?",
            "answer_note": "What have you learned so far?",
        }
        widgets = {
            "question": forms.Textarea(attrs={"rows": 2}),
            "why_it_matters": forms.Textarea(attrs={"rows": 2}),
            "answer_note": forms.Textarea(attrs={"rows": 2}),
        }


class LearningLogEntryForm(forms.ModelForm):
    """"+ Record Learning" -- the OBSERVE -> LEARN -> ADAPT loop. Evidence
    is picked from documents already uploaded to this programme, never a
    fresh upload field of its own."""

    class Meta:
        model = LearningLogEntry
        fields = [
            "date", "project", "activity", "entry_type",
            "what_happened", "what_changed", "what_we_learned", "action_we_will_take", "evidence",
        ]
        labels = {
            "what_happened": "What happened?",
            "what_changed": "What changed?",
            "entry_type": "Type",
            "what_we_learned": "What did we learn?",
            "action_we_will_take": "What action will we take?",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "what_happened": forms.Textarea(attrs={"rows": 2}),
            "what_changed": forms.Textarea(attrs={"rows": 2}),
            "what_we_learned": forms.Textarea(attrs={"rows": 2}),
            "action_we_will_take": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, programme=None, **kwargs):
        super().__init__(*args, **kwargs)
        if programme is not None:
            self.fields["project"].queryset = programme.projects.all()
            self.fields["activity"].queryset = programme.activities.all()
            self.fields["evidence"].queryset = programme.evidence_documents()


class ContextNoteForm(forms.ModelForm):
    class Meta:
        model = ContextNote
        fields = ["category", "description", "date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "date": forms.DateInput(attrs={"type": "date"}),
        }


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
