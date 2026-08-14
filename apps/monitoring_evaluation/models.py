import uuid

from django.db import models

from apps.core.models import TimeStampedModel


class Outcome(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey("programmes.Programme", on_delete=models.CASCADE, related_name="outcomes")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Output(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey("programmes.Programme", on_delete=models.CASCADE, related_name="outputs")
    outcome = models.ForeignKey(Outcome, on_delete=models.SET_NULL, null=True, blank=True, related_name="outputs")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Indicator(TimeStampedModel):
    """A measurable indicator sitting under an outcome or output
    (spec section 27). ``auto_from_attendance`` lets a simple count
    indicator be driven directly from AttendanceRecord totals instead of
    manual capture — but this must be opted into explicitly per indicator,
    never inferred, so unrelated indicators are never silently touched.
    """

    TYPE_NUMERIC = "numeric"
    TYPE_PERCENTAGE = "percentage"
    TYPE_COUNT = "count"
    TYPE_BOOLEAN = "boolean"
    TYPE_QUALITATIVE = "qualitative"
    TYPE_CHOICES = [
        (TYPE_NUMERIC, "Numeric"),
        (TYPE_PERCENTAGE, "Percentage"),
        (TYPE_COUNT, "Count"),
        (TYPE_BOOLEAN, "Boolean (Yes/No)"),
        (TYPE_QUALITATIVE, "Qualitative"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey("programmes.Programme", on_delete=models.CASCADE, related_name="indicators")
    outcome = models.ForeignKey(Outcome, on_delete=models.SET_NULL, null=True, blank=True, related_name="indicators")
    output = models.ForeignKey(Output, on_delete=models.SET_NULL, null=True, blank=True, related_name="indicators")
    name = models.CharField(max_length=255)
    indicator_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default=TYPE_COUNT)
    unit = models.CharField(max_length=50, blank=True)
    baseline_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    target_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    auto_from_attendance = models.BooleanField(default=False, help_text="Actuals are computed from attendance totals for this programme/activity")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def latest_actual(self):
        return self.period_values.order_by("-period_end").first()

    @property
    def achievement_percent(self):
        latest = self.latest_actual
        if not latest or not self.target_value:
            return None
        try:
            return round(float(latest.actual_value) / float(self.target_value) * 100, 1)
        except (ZeroDivisionError, TypeError):
            return None


class IndicatorPeriodValue(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE, related_name="period_values")
    period_start = models.DateField()
    period_end = models.DateField()
    actual_value = models.DecimalField(max_digits=14, decimal_places=2)
    means_of_verification = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    # A target miss is not automatically programme failure -- these let
    # the team explain a result, whatever it is, rather than just
    # reporting a bare number. All optional; nothing here is required to
    # record an actual value.
    contributing_factors = models.TextField(blank=True, help_text="What contributed to this result?")
    learning_note = models.TextField(blank=True, help_text="What did we learn?")
    action_needed = models.TextField(blank=True, help_text="Do we need to change anything?")

    class Meta:
        ordering = ["-period_end"]

    def __str__(self):
        return f"{self.indicator.name}: {self.actual_value} ({self.period_end})"
