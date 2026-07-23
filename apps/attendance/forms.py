from django import forms

from apps.attendance.models import AttendanceRecord


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ["programme", "activity", "beneficiary", "headcount", "attendance_date", "location", "check_in_method"]
        widgets = {"attendance_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            from apps.beneficiaries.models import Beneficiary
            from apps.programmes.models import Activity

            self.fields["programme"].queryset = organisation.programmes.all()
            self.fields["activity"].queryset = Activity.objects.filter(programme__organisation=organisation)
            self.fields["beneficiary"].queryset = Beneficiary.objects.filter(organisation=organisation)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("beneficiary") and cleaned.get("headcount", 1) != 1:
            self.add_error("headcount", "Leave headcount at 1 when recording a named beneficiary.")
        return cleaned


class KioskLaunchForm(forms.Form):
    programme = forms.ModelChoiceField(queryset=None)
    hours_valid = forms.IntegerField(initial=8, min_value=1, max_value=72)

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["programme"].queryset = organisation.programmes.all()
