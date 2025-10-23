from django.contrib import admin
from .models import (
    PurchaseOrder, 
    PurchaseOrderCSV, 
    POBalanceNotification, 
    PurchaseOrderAttachment, 
    PurchaseOrderChangeLog
)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        'po_number', 
        'customer', 
        'account', 
        'currency', 
        'total_amount', 
        'display_remaining_balance', 
        'display_utilization', 
        'status', 
        'valid_from', 
        'valid_until', 
        'created_at'
    ]
    list_filter = ['status', 'currency', 'created_at', 'valid_from', 'valid_until']
    search_fields = ['po_number', 'uuid', 'customer__name', 'account__name']
    readonly_fields = [
        'uuid', 
        'created_at', 
        'updated_at', 
        'display_utilization', 
        'display_remaining_balance', 
        'days_until_expiry'
    ]
    raw_id_fields = ['customer', 'account', 'created_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('uuid', 'po_number', 'customer', 'account')
        }),
        ('Financial Details', {
            'fields': (
                'currency', 
                'total_amount', 
                'spent_amount', 
                'display_remaining_balance', 
                'display_utilization'
            )
        }),
        ('Validity Period', {
            'fields': ('valid_from', 'valid_until', 'days_until_expiry')
        }),
        ('Project & Billing Information', {
            'fields': (
                'project', 
                'sdm', 
                'bill_to', 
                'billing_address',
                'about', 
                'work_done', 
                'comment', 
                'expiration_days',
                'payment_terms', 
                'client_year'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Legacy/Import Fields', {
            'fields': (
                'reference_number', 
                'total_invoiced', 
                'total_tax', 
                'grand_total',
                'supplier_name', 
                'from_company', 
                'requester',
                'department', 
                'project_code', 
                'items_description',
                'delivery_terms', 
                'delivery_date'
            ),
            'classes': ('collapse',)
        }),
        ('Status & Metadata', {
            'fields': ('status', 'created_at', 'updated_at', 'created_by')
        })
    )
    
    def display_remaining_balance(self, obj):
        """Display remaining balance with currency"""
        return f"{obj.currency} {obj.remaining_balance:,.2f}"
    display_remaining_balance.short_description = 'Remaining Balance'
    display_remaining_balance.admin_order_field = 'spent_amount'
    
    def display_utilization(self, obj):
        """Display utilization percentage"""
        return f"{obj.utilization_percentage:.1f}%"
    display_utilization.short_description = 'Utilization'
    
    def save_model(self, request, obj, form, change):
        """Auto-set created_by on new objects"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PurchaseOrderCSV)
class PurchaseOrderCSVAdmin(admin.ModelAdmin):
    list_display = [
        'original_filename', 
        'purchase_order', 
        'extraction_success',
        'uploaded_by', 
        'uploaded_at'
    ]
    list_filter = ['extraction_success', 'uploaded_at']
    search_fields = ['original_filename', 'purchase_order__po_number']
    readonly_fields = ['uploaded_at', 'extracted_data', 'extraction_errors']
    raw_id_fields = ['purchase_order', 'uploaded_by']
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('File Information', {
            'fields': ('csv_file', 'original_filename', 'purchase_order')
        }),
        ('Extraction Results', {
            'fields': ('extraction_success', 'extraction_errors', 'extracted_data')
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'uploaded_at')
        })
    )
    
    def has_add_permission(self, request):
        """Disable manual add - CSVs uploaded through interface"""
        return False


@admin.register(POBalanceNotification)
class POBalanceNotificationAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_order', 
        'threshold_percentage', 
        'utilization_percentage',
        'remaining_balance', 
        'display_priority', 
        'is_read', 
        'created_at'
    ]
    list_filter = ['threshold_percentage', 'is_read', 'created_at']
    search_fields = ['purchase_order__po_number', 'purchase_order__customer__name']
    readonly_fields = ['created_at', 'display_message', 'display_priority']
    raw_id_fields = ['purchase_order']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Details', {
            'fields': (
                'purchase_order', 
                'threshold_percentage', 
                'utilization_percentage', 
                'remaining_balance'
            )
        }),
        ('Display Information', {
            'fields': ('display_message', 'display_priority', 'is_read')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        })
    )
    
    def display_priority(self, obj):
        """Display priority class"""
        return obj.priority_class.upper()
    display_priority.short_description = 'Priority'
    
    def display_message(self, obj):
        """Display notification message"""
        return obj.message
    display_message.short_description = 'Message'
    
    def has_add_permission(self, request):
        """Disable manual add - notifications created by signals"""
        return False


@admin.register(PurchaseOrderAttachment)
class PurchaseOrderAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_order', 
        'original_filename', 
        'description',
        'uploaded_by', 
        'uploaded_at'
    ]
    list_filter = ['uploaded_at']
    search_fields = ['purchase_order__po_number', 'original_filename', 'description']
    readonly_fields = ['uploaded_at']
    raw_id_fields = ['purchase_order', 'uploaded_by']
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('Attachment Information', {
            'fields': ('purchase_order', 'file', 'original_filename', 'description')
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'uploaded_at')
        })
    )
    
    def save_model(self, request, obj, form, change):
        """Auto-set uploaded_by on new objects"""
        if not change:
            obj.uploaded_by = request.user
            # Auto-set original filename if not provided
            if not obj.original_filename and obj.file:
                obj.original_filename = obj.file.name
        super().save_model(request, obj, form, change)


@admin.register(PurchaseOrderChangeLog)
class PurchaseOrderChangeLogAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_order', 
        'field_changed', 
        'display_old_value', 
        'display_new_value',
        'changed_by', 
        'changed_at'
    ]
    list_filter = ['field_changed', 'changed_at']
    search_fields = ['purchase_order__po_number', 'field_changed', 'notes']
    readonly_fields = ['changed_at']
    raw_id_fields = ['purchase_order', 'changed_by']
    date_hierarchy = 'changed_at'
    
    fieldsets = (
        ('Change Information', {
            'fields': (
                'purchase_order', 
                'field_changed', 
                'old_value', 
                'new_value'
            )
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('changed_by', 'changed_at')
        })
    )
    
    def display_old_value(self, obj):
        """Display old value with truncation"""
        if obj.old_value:
            return obj.old_value[:50] + '...' if len(obj.old_value) > 50 else obj.old_value
        return '-'
    display_old_value.short_description = 'Old Value'
    
    def display_new_value(self, obj):
        """Display new value with truncation"""
        if obj.new_value:
            return obj.new_value[:50] + '...' if len(obj.new_value) > 50 else obj.new_value
        return '-'
    display_new_value.short_description = 'New Value'
    
    def has_add_permission(self, request):
        """Disable manual add - change logs created automatically"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing - change logs should be immutable"""
        return False