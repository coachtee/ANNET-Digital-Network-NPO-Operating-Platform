from django import forms

from apps.projects.models import Project, ProjectTask


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "grant", "programme", "manager", "start_date", "end_date", "budget", "status"]
        widgets = {
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
    class Meta:
        model = ProjectTask
        fields = ["title", "assignee", "due_date", "is_milestone", "status"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["assignee"].queryset = self.fields["assignee"].queryset.filter(
                organisation_memberships__organisation=organisation, organisation_memberships__is_active=True
            ).distinct()
