from django.contrib import admin
from .models import RateCard, ServiceRate

class ServiceRateInline(admin.TabularInline):
    model = ServiceRate
    extra = 1

@admin.register(RateCard)
class RateCardAdmin(admin.ModelAdmin):
    list_display = ('customer','region','country','supplier','currency','status','created_at')
    inlines = [ServiceRateInline]

@admin.register(ServiceRate)
class ServiceRateAdmin(admin.ModelAdmin):
    list_display = ('rate_card','category','region','rate_type','rate_value')
