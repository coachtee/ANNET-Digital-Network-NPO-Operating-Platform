from django import forms

from apps.projects.models import Project, ProjectTask


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "name", "objective", "description", "grant", "programme", "manager",
            "location", "start_date", "end_date", "budget", "status",
        ]
        widgets = {
            "objective": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["grant"].queryset = organisation.grants.all()
            self.fields["programme"].queryset = organisation.programmes.all()
            self.fields["manager"].queryset = self.fields["manager"].queryset.filter(
                organisation_memberships__organisation=organisation, organisation_memberships__is_active=True
            ).distinct()

    def clean_programme(self):
        """A Programme must reach minimum readiness (need, purpose,
        beneficiaries, geography, and at least one Outcome/Output/
        Indicator/Target) before a Project can be *created* under it --
        funding is tracked separately and doesn't gate this. Enforced
        here, at the form, so every creation entry point (Projects list,
        the standalone create page, and the wizard's own "add project"
        step) gets the same rule for free. Only checked when the
        programme assignment is actually new/changing -- editing an
        existing project that already belongs to that programme must
        never be blocked by this."""
        programme = self.cleaned_data.get("programme")
        previous_programme_id = self.instance.programme_id if self.instance.pk else None
        if programme is not None and programme.id != previous_programme_id:
            from apps.programmes.services import compute_programme_readiness

            readiness = compute_programme_readiness(programme)
            if not readiness["is_ready"]:
                raise forms.ValidationError(
                    "This programme isn't ready for projects yet. Missing: "
                    + ", ".join(readiness["missing"]) + ". Complete the Programme Plan first."
                )
        return programme


class ProjectTaskForm(forms.ModelForm):
    """Internal delivery work -- optionally tied to the one Activity it
    supports (progressively scoped to the parent Project's own
    activities, never an open-ended picker)."""

    class Meta:
        model = ProjectTask
        fields = ["title", "activity", "assignee", "due_date", "is_milestone", "status"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organisation=None, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["assignee"].queryset = self.fields["assignee"].queryset.filter(
                organisation_memberships__organisation=organisation, organisation_memberships__is_active=True
            ).distinct()
        if project is not None:
            self.fields["activity"].queryset = project.activities.all()
        else:
            self.fields["activity"].queryset = self.fields["activity"].queryset.none()
