from django import forms

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


class ProgrammeCreateForm(forms.ModelForm):
    """The entire "New Programme" experience: a short create form, not a
    multi-step wizard. Everything else (need, purpose, beneficiaries,
    geography, outcomes, team, funding...) is filled in progressively
    inside the Programme Workspace afterwards -- see ProgrammePlanForm,
    the M&E tab and the Team tab."""

    class Meta:
        model = Programme
        fields = ["name", "programme_area", "status", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class ProgrammePlanForm(forms.ModelForm):
    """Plan tab edit form -- where a Programme's need, purpose,
    beneficiaries, geography, staffing and funding are progressively
    filled in after the short Create Programme step."""

    target_beneficiary_groups = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        label="Who will benefit?", help_text="Comma-separated, e.g. Youth aged 18-35, Unemployed graduates",
    )
    locations = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
        label="Where, more specifically?", help_text="District/municipality/locality/venue, comma-separated",
    )

    class Meta:
        model = Programme
        fields = [
            "need_and_background", "theory_of_change_summary", "programme_area", "province",
            "start_date", "end_date", "staffing_plan", "grants",
        ]
        labels = {
            "need_and_background": "What problem are you trying to address?",
            "theory_of_change_summary": "What do you want to achieve?",
            "province": "Primary province",
            "staffing_plan": "Who will deliver this programme, and what resources do they need?",
            "grants": "Which funding sources support this programme?",
        }
        widgets = {
            "need_and_background": forms.Textarea(attrs={"rows": 4}),
            "theory_of_change_summary": forms.Textarea(attrs={"rows": 3}),
            "staffing_plan": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["target_beneficiary_groups"].initial = ", ".join(self.instance.target_beneficiary_groups)
            self.fields["locations"].initial = ", ".join(self.instance.locations)
        if organisation is not None:
            self.fields["grants"].queryset = organisation.grants.all()

    def save(self, commit=True):
        programme = super().save(commit=False)
        programme.target_beneficiary_groups = _to_list(self.cleaned_data["target_beneficiary_groups"])
        programme.locations = _to_list(self.cleaned_data["locations"])
        if commit:
            programme.save()
            self.save_m2m()
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
