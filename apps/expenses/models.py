import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.storage import private_storage


class Budget(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="project_budget")
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def __str__(self):
        return f"Budget: {self.project.name}"

    @property
    def total_recorded_expenditure(self):
        return self.project.expenses.filter(status=Expense.STATUS_APPROVED).aggregate(
            total=models.Sum("amount")
        )["total"] or 0


class BudgetLine(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="lines")
    category = models.CharField(max_length=150)
    allocated_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["category"]

    def __str__(self):
        return f"{self.category} — {self.allocated_amount}"

    @property
    def recorded_expenditure(self):
        return self.expenses.filter(status=Expense.STATUS_APPROVED).aggregate(total=models.Sum("amount"))["total"] or 0


class Expense(TimeStampedModel):
    """Finance Lite expense claim (spec section 30). Not an accounting
    system: this tracks budget vs. recorded expenditure with receipt
    evidence and an approval trail, nothing more.
    """

    STATUS_SUBMITTED = "submitted"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="expenses")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="expenses")
    budget_line = models.ForeignKey(BudgetLine, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="expenses_submitted")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    receipt = models.FileField(upload_to="expense_receipts/%Y/%m/", storage=private_storage)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.description} — R{self.amount}"

    def clean(self):
        # Self-approval prevention (spec section 30/52 release blocker).
        if self.reviewed_by_id and self.submitted_by_id and self.reviewed_by_id == self.submitted_by_id:
            raise ValidationError("A submitter cannot approve or reject their own expense claim.")
