from django.contrib import admin

from apps.expenses.models import Budget, BudgetLine, Expense


class BudgetLineInline(admin.TabularInline):
    model = BudgetLine
    extra = 0


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["project", "total_amount"]
    inlines = [BudgetLineInline]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["description", "project", "amount", "status", "submitted_by", "reviewed_by"]
    list_filter = ["status"]
