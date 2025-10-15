from django.contrib import admin
from .models import RateCard

@admin.register(RateCard)
class RateCardAdmin(admin.ModelAdmin):
    list_display = ['name', 'customer', 'rate_per_unit', 'unit_type', 
                    'valid_from', 'valid_until', 'is_active', 'created_at']
    list_filter = ['is_active', 'unit_type', 'created_at']
    search_fields = ['name', 'customer__name', 'customer__code']
    readonly_fields = ['created_at', 'created_by']
    raw_id_fields = ['customer']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)