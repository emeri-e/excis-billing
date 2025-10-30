from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class Customer(models.Model):
    """Main customer/brand entity (e.g., HCL Technologies, Cognizant)"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_customers')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_account_count(self):
        """Get total number of accounts for this customer"""
        return self.accounts.filter(is_active=True).count()



class Country(models.Model):
    """Country model for account organization"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True, help_text="ISO 3166-1 alpha-3 code")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Countries"
    
    def __str__(self):
        return self.name


class Currency(models.Model):
    """Currency model for flexible currency management"""
    code = models.CharField(max_length=3, unique=True, help_text="ISO 4217 currency code (e.g., USD, EUR)")
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['code']
        verbose_name_plural = "Currencies"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class BillingCycle(models.Model):
    """Billing cycle configurations"""
    CYCLE_TYPES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('bi_monthly', 'Bi-Monthly'),
        ('quarterly', 'Quarterly'),
        ('bi_annually', 'Bi-Annually'),
        ('annually', 'Annually'),
    ]
    
    name = models.CharField(max_length=100)
    cycle_type = models.CharField(max_length=20, choices=CYCLE_TYPES)
    
    # Optional associations - use unique related_names to avoid conflicts
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, 
                                 related_name='associated_billing_cycles')
    account = models.ForeignKey('Account', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='associated_billing_cycles')
    
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        parts = [self.name]
        if self.customer:
            parts.append(f"({self.customer.code}")
        return " ".join(parts)


class Account(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('missing_po', 'Missing PO'),
        ('low_po_balance', 'Low PO Balance'),
    ]
    
    # Basic Information
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='accounts')

    name = models.CharField(max_length=200)
    account_id = models.CharField(max_length=100, unique=True)
    
    # Location - now using text input for region and FK for country
    region = models.CharField(max_length=100, help_text="Region name (e.g., North America, EMEA)")
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='accounts')
    
    # Billing Configuration - use 'accounts' as related_name for reverse lookups
    billing_cycle = models.ForeignKey(BillingCycle, on_delete=models.CASCADE, related_name='accounts')
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name='accounts')
    
    # Status and Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_billing_run = models.DateField(blank=True, null=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_accounts')
    is_active = models.BooleanField(default=True)
    
    # Additional fields for contact info
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('customer', 'account_id')]

    def __str__(self):
        return f"{self.account_id} - {self.name}"
    
    @property
    def active_purchase_order(self):
        """Get the currently active purchase order for this account"""
        try:
            return self.purchase_orders.filter(status='active').first()
        except:
            return None
    
    @property
    def po_balance(self):
        """Get the remaining balance from active PO"""
        active_po = self.active_purchase_order
        return active_po.remaining_balance if active_po else None
    
    @property
    def active_pos_count(self):
        """Count of active purchase orders"""
        try:
            return self.purchase_orders.filter(status='active').count()
        except:
            return 0
    
    @property
    def total_po_value(self):
        """Total value of all purchase orders"""
        try:
            return sum(po.total_amount for po in self.purchase_orders.all() if po.total_amount)
        except:
            return 0
    
    @property
    def remaining_balance(self):
        """Total remaining balance across all purchase orders"""
        try:
            return sum(po.remaining_balance for po in self.purchase_orders.all() if po.remaining_balance)
        except:
            return 0
    
    @property
    def get_formatted_balance(self):
        """Get formatted balance with currency"""
        balance = self.po_balance
        if balance is None:
            return "—"
        
        try:
            symbol = self.currency.symbol if self.currency.symbol else self.currency.code
            return f"{symbol}{balance:,.0f}"
        except:
            return f"{self.currency.code} {balance}"
    
    def update_status(self):
        """Auto-update account status based on PO status"""
        active_po = self.active_purchase_order
        
        if not active_po:
            self.status = 'inactive'
        elif active_po.remaining_balance <= (active_po.total_amount * Decimal('0.2')):
            self.status = 'low_po_balance'
        else:
            self.status = 'active'
        
        self.save(update_fields=['status'])