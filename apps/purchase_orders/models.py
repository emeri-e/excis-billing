from django.db import models
from django.contrib.auth.models import User
from apps.customers.models import Customer, Account
from datetime import date, datetime
import PyPDF2
import re

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('low_balance', 'Low Balance')
    ]
    
    
    department = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Department',
        help_text='Department responsible for this purchase'
    )
    
    project_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Project Code',
        help_text='Associated project code'
    )
    
    items_description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Items Description',
        help_text='Detailed description of items/services'
    )
    
    # Delivery and payment fields
    delivery_terms = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Delivery Terms',
        help_text='e.g., FOB, CIF, EXW'
    )
    
    payment_terms = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Payment Terms',
        help_text='e.g., Net 30, 50% advance'
    )
    
    delivery_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='Delivery Date'
    )
    
    
    # Basic Information
    po_number = models.CharField(max_length=100, unique=True, blank=True)  # Allow blank for auto-generation
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='purchase_orders')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='purchase_orders', null=True, blank=True)
    
    # Financial Details
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Validity Period
    valid_from = models.DateField()
    valid_until = models.DateField()
    
    # Status and Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Additional fields for enhanced functionality
    notes = models.TextField(blank=True, null=True)
    currency = models.CharField(max_length=3, default='USD', choices=[
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('CAD', 'Canadian Dollar'),
        ('AUD', 'Australian Dollar'),
        ('INR', 'Indian Rupee'),
        ('JPY', 'Japanese Yen'),
        ('THB', 'Thai Baht'),
        ('MYR', 'Malaysian Ringgit'),
        ('SGD', 'Singapore Dollar'),
        ('CNY', 'Chinese Yuan'),
        ('HKD', 'Hong Kong Dollar'),
    ])
    
    # Add the missing reference_number field
    reference_number = models.CharField(max_length=100, blank=True, null=True, help_text='Reference number for this PO')

    total_invoiced = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text='Total amount already invoiced')
    total_tax = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text='Estimated total tax')
    grand_total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text='Estimated grand total including tax')
    supplier_name = models.CharField(max_length=255, blank=True, null=True, help_text='Supplier name from PDF')
    from_company = models.CharField(max_length=255, blank=True, null=True, help_text='Ordering company from PDF')
    payment_terms = models.CharField(max_length=100, blank=True, null=True, help_text='Payment terms (e.g., NET 90)')
    requester = models.CharField(max_length=255, blank=True, null=True, help_text='Person who requested the PO')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'valid_until']),
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['po_number']), 
        ]

    def __str__(self):
        if self.account:
            return f"{self.po_number} - {self.account.name}"
        return f"{self.po_number} - {self.customer.name}"
        
    @property
    def utilization_percentage(self):
        """Calculate utilization percentage"""
        if self.total_amount > 0:
            used_amount = self.total_amount - self.remaining_balance
            return (used_amount / self.total_amount) * 100
        return 0
        
    @property
    def days_until_expiry(self):
        """Calculate days until expiry"""
        return (self.valid_until - date.today()).days
    
    @property
    def is_low_balance(self):
        """Check if PO has low balance (less than 20% remaining)"""
        return self.utilization_percentage >= 80
    
    @property
    def is_expiring_soon(self):
        """Check if PO is expiring within 30 days"""
        return 0 <= self.days_until_expiry <= 30
    
    @property
    def is_expired(self):
        """Check if PO has expired"""
        return self.days_until_expiry < 0
    
    @property
    def formatted_amount(self):
        """Get formatted amount with currency"""
        return f"{self.currency} {self.total_amount:,.2f}"
    
    @property
    def formatted_balance(self):
        """Get formatted remaining balance with currency"""
        return f"{self.currency} {self.remaining_balance:,.2f}"
    
    def get_customer_account_display(self):
        """Get display string for customer and account"""
        if self.account:
            return f"{self.customer.name} → {self.account.name}"
        return self.customer.name
    
    def update_status(self):
        """Auto-update status based on current conditions"""
        if self.is_expired:
            self.status = 'expired'
        elif self.remaining_balance <= 0:
            self.status = 'expired'
        elif self.is_low_balance:  # Check this before expiring_soon
            self.status = 'low_balance'
        elif self.is_expiring_soon:
            self.status = 'expiring_soon'
        else:
            self.status = 'active'
    
    def can_be_billed(self):
        """Check if PO can be used for billing"""
        return self.status in ['active', 'expiring_soon'] and self.remaining_balance > 0
    
    def get_billing_runs_summary(self):
        """Get summary of billing runs for this PO"""
        billing_runs = self.billingrun_set.all()
        return {
            'total_runs': billing_runs.count(),
            'completed_runs': billing_runs.filter(status='completed').count(),
            'total_billed': sum(br.amount for br in billing_runs.filter(status='completed')),
            'pending_amount': sum(br.amount for br in billing_runs.filter(status='pending')),
        }
    
    def save(self, *args, **kwargs):
        # Auto-generate PO number if not provided
        if not self.po_number:
            self.po_number = self.generate_po_number()
        
        # Auto-update status based on dates and balance
        if not kwargs.get('skip_status_update', False):
            self.update_status()
        
        super().save(*args, **kwargs)
        
        # Update related account status if account exists
        if self.account:
            self.account.update_status()
    
    def generate_po_number(self):
        """Generate a unique PO number"""
        import uuid
        
        # Get customer code (first 3 letters of name)
        customer_code = self.customer.name[:3].upper() if self.customer else 'PO'
        year = date.today().year
        random_suffix = str(uuid.uuid4())[:6].upper()
        
        po_number = f"PO-{customer_code}-{year}-{random_suffix}"
        
        # Ensure uniqueness
        counter = 1
        original_po_number = po_number
        while PurchaseOrder.objects.filter(po_number=po_number).exists():
            po_number = f"{original_po_number}-{counter}"
            counter += 1
            
        return po_number


class PurchaseOrderAttachment(models.Model):
    """File attachments for purchase orders"""
    purchase_order = models.ForeignKey(PurchaseOrder, related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to='purchase_orders/attachments/')
    original_filename = models.CharField(max_length=255)
    description = models.CharField(max_length=500, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.original_filename}"


class PurchaseOrderChangeLog(models.Model):
    """Track changes to purchase orders"""
    purchase_order = models.ForeignKey(PurchaseOrder, related_name='change_logs', on_delete=models.CASCADE)
    field_changed = models.CharField(max_length=50)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.field_changed} changed"


class POBalanceNotification(models.Model):
    """Notifications for PO balance thresholds"""
    THRESHOLD_CHOICES = [
        (50, '50% Used'),
        (75, '75% Used'), 
        (90, '90% Used - Low Balance'),
    ]
    
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='balance_notifications')
    threshold_percentage = models.IntegerField(choices=THRESHOLD_CHOICES)
    utilization_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        # Prevent duplicate notifications for same PO and threshold
        unique_together = ['purchase_order', 'threshold_percentage']
    
    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.threshold_percentage}% threshold"
    
    @property
    def message(self):
        if self.threshold_percentage == 90:
            return f"⚠️ Critical: PO {self.purchase_order.po_number} is at {self.utilization_percentage}% utilization (Low Balance)"
        elif self.threshold_percentage == 75:
            return f"⚡ Warning: PO {self.purchase_order.po_number} is at {self.utilization_percentage}% utilization"
        else:
            return f"ℹ️ Notice: PO {self.purchase_order.po_number} is at {self.utilization_percentage}% utilization"
    
    @property
    def priority_class(self):
        if self.threshold_percentage == 90:
            return 'critical'
        elif self.threshold_percentage == 75:
            return 'warning' 
        else:
            return 'info'


class PurchaseOrderPDF(models.Model):
    """Store uploaded PDFs and their parsed data"""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='pdf_uploads', null=True, blank=True)
    pdf_file = models.FileField(upload_to='purchase_orders/pdfs/')
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Extracted fields
    extracted_data = models.JSONField(default=dict, blank=True)
    extraction_success = models.BooleanField(default=False)
    extraction_errors = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"PDF for {self.purchase_order.po_number if self.purchase_order else 'New PO'}"
    
    def extract_pdf_data(self):
        """Enhanced PDF data extraction specifically for this PO format"""
        extracted_data = {}
        
        try:
            with open(self.pdf_file.path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                full_text = ""
                
                # Extract text from all pages
                for page in pdf_reader.pages:
                    full_text += page.extract_text() + "\n"
                
                # Clean up the text for better parsing
                text = self.clean_text(full_text)
                
                # Extract key information using targeted patterns
                extracted_data.update(self.extract_basic_info(text))
                extracted_data.update(self.extract_financial_info(text))
                extracted_data.update(self.extract_dates(text))
                extracted_data.update(self.extract_parties_info(text))
                extracted_data.update(self.extract_additional_info(text))
                
                self.extraction_success = True
                self.extracted_data = extracted_data
                self.save()

                return extracted_data
                
        except Exception as e:
            self.extraction_success = False
            self.extraction_errors = str(e)
            self.save()
            return {}

    def clean_text(self, text):
        """Clean and normalize the text"""
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        # Fix common OCR issues
        text = text.replace('RM ', 'RM')
        text = text.replace('MYR ', 'MYR')
        return text

    def extract_basic_info(self, text):
        """Extract basic PO information"""
        data = {}
        
        # Extract PO Number - very specific pattern for this format
        po_match = re.search(r'Purchase Order:\s*([A-Za-z0-9\-]+)', text)
        if po_match:
            data['reference_number'] = po_match.group(1).strip()

        # Extract currency (MYR is Malaysian Ringgit)
        data['currency'] = 'MYR'  # Default for this format
        
        return data

    def extract_financial_info(self, text):
        """Extract financial information"""
        data = {}
        
        # Look for the line item table section
        line_item_section = self.find_line_item_section(text)
        
        if line_item_section:
            # Extract subtotal from line item
            subtotal_match = re.search(r'RM([\d,]+\.?\d*)\s*MYR', line_item_section)
        if subtotal_match:
            subtotal = subtotal_match.group(1).replace(',', '')
            try:
                data['total_amount'] = float(subtotal)
            except ValueError:
                pass
        
        # Extract tax amount
        tax_match = re.search(r'Tax Amount[^\d]*RM([\d,]+\.?\d*)\s*MYR', text)
        if not tax_match:
            tax_match = re.search(r'Est\. Total Tax[^\d]*RM([\d,]+\.?\d*)\s*MYR', text)
        
        if tax_match:
            tax_amount = tax_match.group(1).replace(',', '')
            try:
                data['total_tax'] = float(tax_amount)
            except ValueError:
                pass
        
        # Extract invoiced amount
        invoiced_match = re.search(r'Invoiced Amount[^\d]*RM([\d,]+\.?\d*)\s*MYR', text)
        if invoiced_match:
            invoiced_amount = invoiced_match.group(1).replace(',', '')
            try:
                data['total_invoiced'] = float(invoiced_amount)
                
                # Calculate remaining balance
                if 'total_amount' in data:
                    remaining = data['total_amount'] - data['total_invoiced']
                    data['balance'] = max(0, remaining)
            except ValueError:
                pass

        # Extract grand total
        grand_total_match = re.search(r'Est\. Grand Total[^\d]*RM([\d,]+\.?\d*)\s*MYR', text)
        if grand_total_match:
            grand_total = grand_total_match.group(1).replace(',', '')
            try:
                data['grand_total'] = float(grand_total)
            except ValueError:
                pass
        
        # Extract payment terms
        payment_terms_match = re.search(r'Payment Terms\s*(NET \d+)', text)
        if payment_terms_match:
            data['payment_terms'] = payment_terms_match.group(1).strip()
        
        return data

    def find_line_item_section(self, text):
        """Find and extract the line item table section"""
        # Look for the line item header pattern
        line_start = re.search(r'Line\s*#.*?Price.*?Subtotal', text, re.IGNORECASE)
        if line_start:
            # Get text from line items start to the next major section
            section_start = line_start.start()
            section_end = text.find('STATUS', section_start)
            if section_end == -1:
                section_end = text.find('Tax Category', section_start)
            if section_end == -1:
                section_end = section_start + 1000  # Limit search area
            
            return text[section_start:section_end]
        return ""

    def extract_dates(self, text):
        """Extract date information"""
        data = {}
        
        # Extract service period dates
        start_match = re.search(r'Service Start Date[:\s]*(\d{1,2}\s+[A-Za-z]+\s+\d{4})', text)
        end_match = re.search(r'Service End Date[:\s]*(\d{1,2}\s+[A-Za-z]+\s+\d{4})', text)
        
        if start_match:
            start_date_str = start_match.group(1)
            try:
                # Parse date like "1 Apr 2025"
                start_date = datetime.strptime(start_date_str, '%d %b %Y')
                data['valid_from'] = start_date.strftime('%Y-%m-%d')
                data['service_start_date'] = data['valid_from']
            except ValueError:
                pass
        
        if end_match:
            end_date_str = end_match.group(1)
            try:
                # Parse date like "31 Mar 2026"
                end_date = datetime.strptime(end_date_str, '%d %b %Y')
                data['valid_until'] = end_date.strftime('%Y-%m-%d')
                data['service_end_date'] = data['valid_until']
            except ValueError:
                pass
        
        # Extract order date
        order_date_match = re.search(r'Order submitted on[:\s]*([A-Za-z]+\s+\d+\s+[A-Za-z]+\s+\d{4})', text)
        if order_date_match:
            order_date_str = order_date_match.group(1)
            try:
                # Parse date like "Friday 4 Jul 2025"
                order_date = datetime.strptime(order_date_str, '%A %d %b %Y')
                data['order_date'] = order_date.strftime('%Y-%m-%d')
            except ValueError:
                pass
        
        return data

    def extract_parties_info(self, text):
        """Extract information about parties involved"""
        data = {}
        
        # Extract supplier information
        supplier_match = re.search(r'To:\s*([^\n]+)\s*(\d+[^\n]*Kuala Lumpur[^\n]*Malaysia)', text)
        if supplier_match:
            supplier_name = supplier_match.group(1).strip()
            data['supplier'] = supplier_name
            
            # Check if this matches any customer in database
            try:
                from apps.customers.models import Customer
                # Try to find matching customer
                customer_match = Customer.objects.filter(
                    name__icontains=supplier_name.split()[0],  # First word
                    is_active=True
                ).first()
                
                if customer_match:
                    data['matched_customer_id'] = customer_match.id
                    data['matched_customer_name'] = customer_match.name
            except Exception as e:
                pass

        # Extract from company (buyer)
        from_match = re.search(r'From:\s*\(([^)]+)\)\s*([^\n]+)', text)
        if from_match:
            from_company_code = from_match.group(1).strip()
            from_company_name = from_match.group(2).strip()
            data['from_company'] = f"{from_company_code} - {from_company_name}"
        
        # Extract requester
        requester_match = re.search(r'Requester:\s*([^\n]+)', text)
        if requester_match:
            data['requester'] = requester_match.group(1).strip()
        
        return data

    def extract_additional_info(self, text):
        """Extract additional information"""
        data = {}
        
        # Extract description from line items
        desc_match = re.search(r'Part\s*#\s*/\s*Description[^\n]*\n[^\n]*Not Available[^\n]*\n[^\n]*([^\n|]+)', text)
        if desc_match:
            description = desc_match.group(1).strip()
            data['description'] = description
            data['items_description'] = description
        
        # Extract quantity
        qty_match = re.search(r'Qty\s*\(Unit\)[^\n]*\n[^\n]*\|\s*(\d+)\s*\(', text)
        if qty_match:
            data['quantity'] = int(qty_match.group(1))
        
        
        # Extract billing frequency
        billing_match = re.search(r'BillingFrequency[:\s]*([^\n]+)', text)
        if billing_match:
            data['billing_frequency'] = billing_match.group(1).strip()
        
        return data
    
    def parse_pdf_text(self, text):
        """Parse PDF text to extract PO information - Enhanced for HCL format"""
        data = {}
        try:
            # 1. Extract Purchase Order Number
            # Matches: "Purchase Order: 9200143147" or "9200143147" at start
            order_patterns = [
                r'Purchase\s+Order:\s*(\d+)',
                r'^\s*(\d{10,})',  # 10+ digit number at start of line
                r'ORDER\s+NO\.?\s*([A-Za-z0-9\-]+)',
                r'Order\s+Number:?\s*([A-Za-z0-9\-]+)',
                r'PO\s+Number:?\s*([A-Za-z0-9\-]+)'
            ]
            
            for pattern in order_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    data['reference_number'] = match.group(1).strip()
                    break
            
            # 2. Extract Currency and Amounts
            # Look for Sub-total, Total Invoiced, Est. Total Tax, Est. Grand Total
            
            # Sub-total (main amount)
            subtotal_patterns = [
                r'Sub-total:\s*([A-Z]{3})\s*([\d,]+\.?\d*)',  # "Sub-total: RM 75,551.00 MYR"
                r'Sub-total:\s*([\d,]+\.?\d*)\s*([A-Z]{3})',
                r'Amount:\s*([A-Z]{3})\s*([\d,]+\.?\d*)',     # "Amount: RM 75,551.00 MYR"
                r'TOTAL\s+AMOUNT\s*([\d,]+\.?\d*)\s*([A-Z]{3})',
            ]
            
            for pattern in subtotal_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        group1, group2 = match.group(1), match.group(2)
                        
                        # Determine which group is currency and which is amount
                        if group1.isalpha() and len(group1) == 3:
                            data['currency'] = group1.upper()
                            amount_str = group2.replace(',', '')
                            data['total_amount'] = float(amount_str)
                        else:
                            amount_str = group1.replace(',', '')
                            data['total_amount'] = float(amount_str)
                            data['currency'] = group2.upper()
                        break
                    except (ValueError, AttributeError):
                        continue
            
            # Total Invoiced
            invoiced_patterns = [
                r'Total\s+Invoiced:\s*([A-Z]{3})?\s*([\d,]+\.?\d*)\s*([A-Z]{3})?',
                r'Invoiced\s+Amount:\s*([A-Z]{3})?\s*([\d,]+\.?\d*)\s*([A-Z]{3})?',
            ]
            
            for pattern in invoiced_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        # Extract amount (group 2 is always the number)
                        amount_str = match.group(2).replace(',', '')
                        data['total_invoiced'] = float(amount_str)
                        
                        # Extract currency if not already set
                        if 'currency' not in data:
                            currency = match.group(1) or match.group(3)
                            if currency:
                                data['currency'] = currency.upper()
                        break
                    except (ValueError, AttributeError):
                        continue
            
            # Est. Total Tax
            tax_patterns = [
                r'Est\.\s+Total\s+Tax:\s*([A-Z]{3})?\s*([\d,]+\.?\d*)\s*([A-Z]{3})?',
                r'Total\s+Tax:\s*([A-Z]{3})?\s*([\d,]+\.?\d*)\s*([A-Z]{3})?',
            ]
            
            for pattern in tax_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        amount_str = match.group(2).replace(',', '')
                        data['total_tax'] = float(amount_str)
                        break
                    except (ValueError, AttributeError):
                        continue
            
            # Est. Grand Total
            grand_total_patterns = [
                r'Est\.\s+Grand\s+Total:\s*([A-Z]{3})?\s*([\d,]+\.?\d*)\s*([A-Z]{3})?',
                r'Grand\s+Total:\s*([A-Z]{3})?\s*([\d,]+\.?\d*)\s*([A-Z]{3})?',
            ]
            
            for pattern in grand_total_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        amount_str = match.group(2).replace(',', '')
                        data['grand_total'] = float(amount_str)
                        break
                    except (ValueError, AttributeError):
                        continue
            
            # 3. Extract Service Start Date
            # Matches various formats including "1 Apr 2025", "Tue, 1 Apr, 2025"
            start_date_patterns = [
                r'Service\s+Start\s+Date:\s*(?:\w+,?\s*)?(\d{1,2}\s+\w+,?\s+\d{4})',  # "1 Apr 2025" or "Tue, 1 Apr, 2025"
                r'Service\s+Start\s+Date:\s*\w+\s*,\s*(\w+\s+\d{1,2}\s*,\s*\d{4})',   # "Monday, August 25, 2025"
                r'Start\s+Date:\s*(?:\w+,?\s*)?(\d{1,2}\s+\w+,?\s+\d{4})',
                r'Valid\s+From:\s*(?:\w+,?\s*)?(\d{1,2}\s+\w+,?\s+\d{4})',
            ]
            
            for pattern in start_date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        date_str = match.group(1).strip()
                        # Remove commas and normalize spaces
                        date_str = date_str.replace(',', '').strip()
                        date_str = re.sub(r'\s+', ' ', date_str)
                        
                        # Try different date formats
                        for date_format in ['%d %b %Y', '%B %d %Y', '%d %B %Y']:
                            try:
                                parsed_date = datetime.strptime(date_str, date_format)
                                data['valid_from'] = parsed_date.strftime('%Y-%m-%d')
                                break
                            except ValueError:
                                continue
                        
                        if 'valid_from' in data:
                            break
                    except Exception:
                        continue
            
            # 4. Extract Service End Date
            # Matches various formats
            end_date_patterns = [
                r'Service\s+End\s+Date:\s*(?:\w+,?\s*)?(\d{1,2}\s+\w+,?\s+\d{4})',  # "31 Mar 2026" or "Tue, 31 Mar, 2026"
                r'Service\s+End\s+Date:\s*\w+\s*,\s*(\w+\s+\d{1,2}\s*,\s*\d{4})',   # "Tuesday, March 31, 2026"
                r'End\s+Date:\s*(?:\w+,?\s*)?(\d{1,2}\s+\w+,?\s+\d{4})',
                r'Valid\s+Until:\s*(?:\w+,?\s*)?(\d{1,2}\s+\w+,?\s+\d{4})',
            ]
            
            for pattern in end_date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        date_str = match.group(1).strip()
                        # Remove commas and normalize spaces
                        date_str = date_str.replace(',', '').strip()
                        date_str = re.sub(r'\s+', ' ', date_str)
                        
                        # Try different date formats
                        for date_format in ['%d %b %Y', '%B %d %Y', '%d %B %Y']:
                            try:
                                parsed_date = datetime.strptime(date_str, date_format)
                                data['valid_until'] = parsed_date.strftime('%Y-%m-%d')
                                break
                            except ValueError:
                                continue
                        
                        if 'valid_until' in data:
                            break
                    except Exception:
                        continue
            
            # 5. Extract Supplier Information
            supplier_patterns = [
                r'To:\s*([^\n]+(?:\n(?!From:|Payment|Comments)[^\n]+)*)',  # Multi-line after "To:"
                r'SUPPLIER:\s*([^\n\r]+)',
                r'Supplier:\s*([^\n\r]+)',
                r'Vendor:\s*([^\n\r]+)',
            ]
            
            for pattern in supplier_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    supplier_text = match.group(1).strip()
                    # Take first line as supplier name
                    supplier_lines = [line.strip() for line in supplier_text.split('\n') if line.strip()]
                    if supplier_lines:
                        data['supplier'] = supplier_lines[0]
                        break
            
            # 6. Extract Description from Line Items
            description_patterns = [
                r'Part\s+#\s+/\s+Description[^\n]*\n[^\n]*\n[^\n]*\n\s*(.+?)(?:\n|STATUS)',  # After header
                r'Line\s+Items[^\n]*\n[^\n]*\n[^\n]*(.+?)(?:\n\n|STATUS)',
                r'Description[^\n]*\n\s*([^\n]+)',
            ]
            
            for pattern in description_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    description = match.group(1).strip()
                    # Clean up the description
                    description = re.sub(r'\s+', ' ', description)
                    description = re.sub(r'^[0-9\s]+', '', description)
                    if len(description) > 3:
                        data['description'] = description[:200]  # Limit length
                        break
            
            # 7. Extract Payment Terms
            payment_terms_match = re.search(r'Payment\s+Terms[:\s]*([^\n\r]+)', text, re.IGNORECASE)
            if payment_terms_match:
                data['payment_terms'] = payment_terms_match.group(1).strip()
            
            # 8. Extract Requester
            requester_patterns = [
                r'Requester:\s*([^\n\r]+)',
                r'Req\.\s+Line\s+No\.:[^\n]*\n\s*Requester:\s*([^\n\r]+)',
            ]
            
            for pattern in requester_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    requester = match.group(1).strip()
                    # Remove employee ID if present (e.g., "Ram Shyam Pandey-52051089" -> "Ram Shyam Pandey")
                    requester = re.sub(r'-\d+$', '', requester).strip()
                    data['requester'] = requester
                    break
            
            # 9. Extract Company/From information
            from_match = re.search(r'From:\s*([^\n]+)', text, re.IGNORECASE)
            if from_match:
                data['from_company'] = from_match.group(1).strip()
        
        except Exception as e:
            return {}
        
        return data