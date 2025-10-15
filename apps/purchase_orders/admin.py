from django.contrib import admin
from .models import PurchaseOrder

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['po_number', 'customer', 'total_amount', 'remaining_balance', 
                    'status', 'valid_from', 'valid_until', 'created_at']
    list_filter = ['status', 'created_at', 'valid_from', 'valid_until']
    search_fields = ['po_number', 'customer__name', 'customer__code']
    readonly_fields = ['created_at', 'created_by', 'utilization_percentage']
    raw_id_fields = ['customer']
    
    fieldsets = (
        (None, {
            'fields': ('po_number', 'customer', 'status')
        }),
        ('Financial Details', {
            'fields': ('total_amount', 'remaining_balance', 'utilization_percentage')
        }),
        ('Validity Period', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('System Information', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            if not obj.remaining_balance:
                obj.remaining_balance = obj.total_amount
        super().save_model(request, obj, form, change)