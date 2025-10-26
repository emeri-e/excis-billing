from django.contrib import admin
from .models import RateCard, ServiceRate, DedicatedRate, ScheduledRate, DispatchRate, ProjectRate

class RateInline(admin.TabularInline):
    model = ServiceRate
    extra = 0

@admin.register(RateCard)
class RateCardAdmin(admin.ModelAdmin):
    list_display = ('customer','region','country','supplier','currency','status','created_at')
    inlines = [RateInline]


@admin.register(ServiceRate)
class ServiceRateAdmin(admin.ModelAdmin):
    list_display = ('id','rate_card','category','rate_type','rate_value')

@admin.register(DedicatedRate)
class DedicatedRateAdmin(admin.ModelAdmin):
    list_display = ('id','rate_card','category','rate_type','rate_value')

@admin.register(ScheduledRate)
class ScheduledRateAdmin(admin.ModelAdmin):
    list_display = ('id','rate_card','category','rate_type','rate_value')

@admin.register(DispatchRate)
class DispatchRateAdmin(admin.ModelAdmin):
    list_display = ('id','rate_card','category','rate_type','rate_value')

@admin.register(ProjectRate)
class ProjectRateAdmin(admin.ModelAdmin):
    list_display = ('id','rate_card','category','rate_type','rate_value')
