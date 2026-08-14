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
