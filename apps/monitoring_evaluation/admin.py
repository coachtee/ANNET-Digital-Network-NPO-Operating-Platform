from django.contrib import admin

from apps.monitoring_evaluation.models import Indicator, IndicatorPeriodValue, Outcome, Output


class IndicatorPeriodValueInline(admin.TabularInline):
    model = IndicatorPeriodValue
    extra = 0


@admin.register(Indicator)
class IndicatorAdmin(admin.ModelAdmin):
    list_display = ["name", "programme", "indicator_type", "baseline_value", "target_value"]
    list_filter = ["indicator_type"]
    inlines = [IndicatorPeriodValueInline]


admin.site.register(Outcome)
admin.site.register(Output)
