from django import forms

from apps.memberships.models import MembershipApplication


class ApplicationMotivationForm(forms.ModelForm):
    class Meta:
        model = MembershipApplication
        fields = ["motivation"]
        widgets = {"motivation": forms.Textarea(attrs={"rows": 5})}


class ApplicationDecisionForm(forms.Form):
    status = forms.ChoiceField(choices=[
        (MembershipApplication.STATUS_INFORMATION_REQUESTED, "Request more information"),
        (MembershipApplication.STATUS_APPROVED, "Approve — Active Member"),
        (MembershipApplication.STATUS_DECLINED, "Decline"),
    ])
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
