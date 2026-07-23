import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Project(TimeStampedModel):
    """Lightweight, NPO-focused project management (spec section 24) —
    deliberately not a general task-tracker: scope is funded delivery."""

    STATUS_PLANNING = "planning"
    STATUS_ACTIVE = "active"
    STATUS_ON_HOLD = "on_hold"
    STATUS_COMPLETE = "complete"
    STATUS_CHOICES = [
        (STATUS_PLANNING, "Planning"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ON_HOLD, "On Hold"),
        (STATUS_COMPLETE, "Complete"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, related_name="projects")
    grant = models.ForeignKey("grants.Grant", on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    programme = models.ForeignKey("programmes.Programme", on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects_managed")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PLANNING)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProjectTask(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=255)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    due_date = models.DateField(null=True, blank=True)
    is_milestone = models.BooleanField(default=False)
    status = models.CharField(
        max_length=15,
        choices=[("todo", "To Do"), ("in_progress", "In Progress"), ("done", "Done"), ("at_risk", "At Risk")],
        default="todo",
    )

    class Meta:
        ordering = ["due_date", "created_at"]

    def __str__(self):
        return self.title
