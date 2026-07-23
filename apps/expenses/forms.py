from django import forms

from apps.core.validators import validate_upload_file
from apps.expenses.models import Budget, BudgetLine, Expense


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["total_amount"]


class BudgetLineForm(forms.ModelForm):
    class Meta:
        model = BudgetLine
        fields = ["category", "allocated_amount"]


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["budget_line", "amount", "description", "receipt"]

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None and hasattr(project, "project_budget"):
            self.fields["budget_line"].queryset = project.project_budget.lines.all()
        else:
            self.fields["budget_line"].queryset = BudgetLine.objects.none()

    def clean_receipt(self):
        receipt = self.cleaned_data["receipt"]
        validate_upload_file(receipt)
        return receipt


class ExpenseReviewForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["status", "review_note"]
        widgets = {"review_note": forms.Textarea(attrs={"rows": 2})}
