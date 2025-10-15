from django.db import models
from django.contrib.auth.models import User
from apps.customers.models import Customer, Account
from apps.purchase_orders.models import PurchaseOrder

class BillingRun(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    BILLING_TYPE_CHOICES = [
        ('manual', 'Manual'),
        ('wizard', 'Wizard'),
        ('automated', 'Automated'),
    ]
    
    # Basic Information
    run_id = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE)
    
    # Billing Details
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    billing_date = models.DateField(auto_now_add=True)
    billing_start_date = models.DateField(null=True, blank=True)
    billing_end_date = models.DateField(null=True, blank=True)
    
    # Processing Information
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    billing_type = models.CharField(max_length=20, choices=BILLING_TYPE_CHOICES, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional Fields
    notes = models.TextField(blank=True, null=True)
    tickets_count = models.IntegerField(default=0)
    rate_card_applied = models.ForeignKey('rate_cards.RateCard', on_delete=models.SET_NULL, null=True, blank=True)
    
    # File Management
    tickets_file = models.FileField(upload_to='billing/tickets/', null=True, blank=True)
    output_file = models.FileField(upload_to='billing/output/', null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['account', 'created_at']),
        ]

    def __str__(self):
        if self.account:
            return f"{self.run_id} - {self.account.name}"
        return f"{self.run_id} - {self.customer.name}"
    
    @property
    def billing_period(self):
        """Return formatted billing period"""
        if self.billing_start_date and self.billing_end_date:
            return f"{self.billing_start_date.strftime('%b %d')} - {self.billing_end_date.strftime('%b %d, %Y')}"
        return f"Single date: {self.billing_date.strftime('%b %d, %Y')}"
    
    @property
    def period_days(self):
        """Calculate number of days in billing period"""
        if self.billing_start_date and self.billing_end_date:
            return (self.billing_end_date - self.billing_start_date).days + 1
        return 1
    
    def can_be_cancelled(self):
        """Check if billing run can be cancelled"""
        return self.status in ['draft', 'pending']
    
    def can_be_processed(self):
        """Check if billing run can be processed"""
        return self.status in ['draft', 'pending']
    
    def get_customer_account_display(self):
        """Get display name for customer and account"""
        if self.account:
            return f"{self.customer.name} → {self.account.name}"
        return self.customer.name
    
    def save(self, *args, **kwargs):
        # Auto-set processed_at when status changes to completed
        if self.status == 'completed' and not self.processed_at:
            from django.utils import timezone
            self.processed_at = timezone.now()
        
        super().save(*args, **kwargs)


class BillingRunLineItem(models.Model):
    """Individual line items within a billing run"""
    billing_run = models.ForeignKey(BillingRun, related_name='line_items', on_delete=models.CASCADE)
    
    # Line Item Details
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_rate = models.DecimalField(max_digits=10, decimal_places=4)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Reference Data
    ticket_reference = models.CharField(max_length=100, blank=True, null=True)
    work_date = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['work_date', 'description']
    
    def __str__(self):
        return f"{self.billing_run.run_id} - {self.description[:50]}"


class BillingRunAttachment(models.Model):
    """File attachments for billing runs"""
    billing_run = models.ForeignKey(BillingRun, related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to='billing/attachments/')
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.billing_run.run_id} - {self.original_filename}"