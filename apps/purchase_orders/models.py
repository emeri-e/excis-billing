from django.db import models
from django.contrib.auth.models import User
from apps.customers.models import Customer, Account
from datetime import date, datetime
import csv
import io
import uuid


class PurchaseOrder(models.Model):
    """Main Purchase Order model"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('low_balance', 'Low Balance'),
        ('expiring_soon', 'Expiring Soon'),
        ('fully_utilized', 'Fully Utilized'),
    ]
    
    # UUID for external reference/tracking (keep integer pk as default)
    uuid = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True,
        db_index=True,
        help_text='Unique identifier for API and external references'
    )
    
    # Core fields
    po_number = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='purchase_orders'
    )
    account = models.ForeignKey(
        Account, 
        on_delete=models.CASCADE, 
        related_name='purchase_orders', 
        null=True, 
        blank=True
    )
    
    # Financial Details
    currency = models.CharField(
        max_length=3, 
        default='USD',
        help_text='3-letter currency code (e.g., USD, EUR, GBP)'
    )
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    spent_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Validity Period
    valid_from = models.DateField()
    valid_until = models.DateField()
    
    # CSV Import Fields (Main additional info)
    project = models.CharField(max_length=200, blank=True, null=True)
    sdm = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        verbose_name='Service Delivery Manager'
    )
    bill_to = models.CharField(max_length=200, blank=True, null=True)
    billing_address = models.TextField(blank=True, null=True)
    about = models.TextField(blank=True, null=True)
    work_done = models.CharField(max_length=50, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    expiration_days = models.IntegerField(blank=True, null=True)
    payment_terms = models.CharField(max_length=100, blank=True, null=True)
    client_year = models.CharField(max_length=4, blank=True, null=True)
    
    # Additional fields
    notes = models.TextField(blank=True, null=True)
    reference_number = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text='Reference number for this PO'
    )
    
    # Legacy fields (for backward compatibility)
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
    delivery_terms = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Delivery Terms',
        help_text='e.g., FOB, CIF, EXW'
    )
    delivery_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='Delivery Date'
    )
    total_invoiced = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text='Total amount already invoiced'
    )
    total_tax = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text='Estimated total tax'
    )
    grand_total = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text='Estimated grand total including tax'
    )
    supplier_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text='Supplier name from CSV/PDF'
    )
    from_company = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text='Ordering company from CSV/PDF'
    )
    requester = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text='Person who requested the PO'
    )
    
    # Status and Metadata
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'valid_until']),
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['po_number']),
            models.Index(fields=['uuid']),
        ]
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'

    def __str__(self):
        if self.account:
            return f"{self.po_number} - {self.account.name}"
        return f"{self.po_number} - {self.customer.name}"
    
    # Calculated Properties
    @property
    def remaining_balance(self):
        """Calculate remaining balance"""
        return max(self.total_amount - self.spent_amount, 0)
    
    @property
    def utilization_percentage(self):
        """Calculate utilization percentage"""
        if self.total_amount > 0:
            return (self.spent_amount / self.total_amount) * 100
        return 0
    
    @property
    def days_until_expiry(self):
        """Calculate days until expiry"""
        return (self.valid_until - date.today()).days
    
    @property
    def is_low_balance(self):
        """Check if PO has low balance (less than 10% remaining)"""
        return self.utilization_percentage >= 90
    
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
    
    @property
    def remaining_balance(self):
        """Calculate remaining balance from total_amount and spent_amount"""
        return self.total_amount - self.spent_amount

    @property
    def utilization_percentage(self):
        """Calculate utilization percentage"""
        if self.total_amount > 0:
            return (self.spent_amount / self.total_amount) * 100
        return 0

    @property
    def formatted_balance(self):
        """Get formatted remaining balance with currency"""
        return f"{self.currency} {self.remaining_balance:,.2f}"
    
    # Helper Methods
    def get_customer_account_display(self):
        """Get display string for customer and account"""
        if self.account:
            return f"{self.customer.name} â†’ {self.account.name}"
        return self.customer.name
    
    def update_status(self):
        """Auto-update status based on current conditions"""
        remaining = self.remaining_balance
        days_left = self.days_until_expiry
        
        if remaining <= 0:
            self.status = 'fully_utilized'
        elif days_left <= 30 and days_left >= 0:
            self.status = 'expiring_soon'
        elif (remaining / self.total_amount) < 0.10:
            self.status = 'low_balance'
        else:
            self.status = 'active'
    
    def can_be_billed(self):
        """Check if PO can be used for billing"""
        return self.status in ['active', 'expiring_soon', 'low_balance'] and self.remaining_balance > 0
    
    def get_billing_runs_summary(self):
        """Get summary of billing runs for this PO"""
        try:
            billing_runs = self.billingrun_set.all()
            return {
                'total_runs': billing_runs.count(),
                'completed_runs': billing_runs.filter(status='completed').count(),
                'total_billed': sum(br.amount for br in billing_runs.filter(status='completed')),
                'pending_amount': sum(br.amount for br in billing_runs.filter(status='pending')),
            }
        except:
            return {
                'total_runs': 0,
                'completed_runs': 0,
                'total_billed': 0,
                'pending_amount': 0,
            }
    
    def generate_po_number(self):
        """Generate a unique PO number"""
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
    
    def save(self, *args, **kwargs):
        """Override save to auto-generate PO number and update status"""
        # Auto-generate PO number if not provided
        if not self.po_number:
            self.po_number = self.generate_po_number()
        
        # Auto-update status based on dates and balance
        if not kwargs.get('skip_status_update', False):
            self.update_status()
        
        super().save(*args, **kwargs)
        
        # Update related account status if account exists
        if self.account:
            try:
                self.account.update_status()
            except:
                pass


class PurchaseOrderCSV(models.Model):
    """Store uploaded CSVs and their parsed data"""
    
    purchase_order = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.CASCADE, 
        related_name='csv_uploads', 
        null=True, 
        blank=True
    )
    csv_file = models.FileField(upload_to='purchase_orders/csvs/')
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Extracted data
    extracted_data = models.JSONField(default=dict, blank=True)
    extraction_success = models.BooleanField(default=False)
    extraction_errors = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Purchase Order CSV'
        verbose_name_plural = 'Purchase Order CSVs'
    
    def __str__(self):
        return f"CSV for {self.purchase_order.po_number if self.purchase_order else 'New PO'}"
    
    def extract_csv_data(self):
        """
        Extract data from HCL PO Report CSV file
        Structure:
        - Row 1: Customer name (e.g., "HCL")
        - Row 6: Headers (PROJECT, SDM, PO NUMBER, etc.)
        - Row 7+: Data rows
        - PROJECT column = Account name
        """
        from datetime import datetime
        
        extracted_data = {
            'customer_name': '',
            'po_records': []
        }
        
        try:
            # Read CSV file with encoding fallback
            self.csv_file.seek(0)
            
            # Try multiple encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
            content = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    self.csv_file.seek(0)
                    content = self.csv_file.read().decode(encoding)
                    used_encoding = encoding
                    break
                except (UnicodeDecodeError, AttributeError):
                    continue
            
            if content is None:
                raise ValueError("Could not decode CSV file with any supported encoding")
            
            # Parse CSV
            csv_reader = csv.reader(io.StringIO(content))
            all_rows = list(csv_reader)
            
            if len(all_rows) < 7:
                raise ValueError("CSV file does not have enough rows (expected at least 7)")
            
            # Extract customer name from first row
            if all_rows[0] and all_rows[0][0]:
                extracted_data['customer_name'] = all_rows[0][0].strip()
            
            # Find header row (should be around row 5-6)
            header_row_idx = None
            headers = []
            
            for idx in range(min(20, len(all_rows))):
                row = all_rows[idx]
                row_text = ' '.join([str(cell) for cell in row if cell])
                if 'PROJECT' in row_text and 'PO NUMBER' in row_text:
                    header_row_idx = idx
                    headers = row
                    break
            
            if header_row_idx is None:
                raise ValueError("Could not find header row with PROJECT and PO NUMBER columns")
            
            # Map column positions - use exact header names
            col_map = {}
            for idx, header in enumerate(headers):
                if header and header.strip():
                    # Clean header (remove BOM and extra whitespace)
                    clean_header = header.strip().replace('\ufeff', '').replace('ï¿½', '')
                    col_map[clean_header] = idx
            
            # Extract data rows
            data_rows = all_rows[header_row_idx + 1:]
            
            # Process each data row
            for row in data_rows:
                if not row or len(row) < 5:
                    continue
                
                # Skip empty rows
                if not any(cell for cell in row):
                    continue
                
                try:
                    record = {}
                    
                    # Helper function to safely get cell value
                    def get_cell(header_name):
                        if header_name in col_map and col_map[header_name] < len(row):
                            value = row[col_map[header_name]]
                            return value.strip() if value else ''
                        return ''
                    
                    # Extract account name from PROJECT column
                    record['account_name'] = get_cell('PROJECT')
                    
                    # Extract PO details
                    record['sdm'] = get_cell('SDM')
                    record['po_number'] = get_cell('PO NUMBER')
                    record['excis_entity'] = get_cell('EXCIS ENTITY')
                    record['bill_to'] = get_cell('BILL TO')
                    record['billing_address'] = get_cell('BILLING ADDRESS')
                    record['about'] = get_cell('ABOUT')
                    record['work_done'] = get_cell('WORK DONE')
                    record['comment'] = get_cell('COMMENT')
                    
                    # Parse dates
                    start_date_str = get_cell('START DATE')
                    if start_date_str:
                        parsed_date = self._parse_date(start_date_str)
                        if parsed_date:
                            record['valid_from'] = parsed_date.strftime('%Y-%m-%d')  # Convert to string for JSON
                    
                    end_date_str = get_cell('END DATE')
                    if end_date_str:
                        parsed_date = self._parse_date(end_date_str)
                        if parsed_date:
                            record['valid_until'] = parsed_date.strftime('%Y-%m-%d')  # Convert to string for JSON
                    
                    exp_str = get_cell('EXPIRATION DAYS')
                    if exp_str:
                        try:
                            record['expiration_days'] = int(exp_str)
                        except (ValueError, AttributeError):
                            record['expiration_days'] = None
                    
                    # Parse financial data
                    po_amount_str = get_cell('PO AMOUNT')
                    if po_amount_str:
                        record['total_amount'] = self._clean_number(po_amount_str)
                    
                    po_balance_str = get_cell('PO BALANCE')
                    if po_balance_str:
                        balance = self._clean_number(po_balance_str)
                        record['remaining_balance'] = balance
                        record['spent_amount'] = record.get('total_amount', 0) - balance
                    
                    currency_str = get_cell('CURRENCY')
                    record['currency'] = currency_str[:3] if currency_str else 'USD'
                    
                    # Additional fields
                    record['payment_terms'] = get_cell('PAYMENT TERMS')
                    record['client_year'] = get_cell('CLIENT YEAR')
                    record['po_status'] = get_cell('PO STATUS')
                    
                    # Only add if has account name or total amount
                    if record.get('account_name') or record.get('total_amount', 0) > 0:
                        extracted_data['po_records'].append(record)
                
                except Exception as e:
                    # Log error but continue processing other rows
                    continue
            
            extracted_data['_encoding_used'] = used_encoding
            extracted_data['_total_records'] = len(extracted_data['po_records'])
            
            self.extraction_success = True
            self.extracted_data = extracted_data
            self.save()
            
            return extracted_data
            
        except Exception as e:
            self.extraction_success = False
            self.extraction_errors = str(e)
            self.save()
            return {}

    def _parse_date(self, date_str):
        """Parse various date formats and return date object"""
        if not date_str or date_str.strip() == '':
            return None
        
        date_formats = [
            '%d-%b-%y',      # 1-Jan-23
            '%d-%b-%Y',      # 1-Jan-2023
            '%d-%m-%Y',      # 01-01-2023
            '%Y-%m-%d',      # 2023-01-01
            '%d/%m/%Y',      # 01/01/2023
            '%m/%d/%Y',      # 01/01/2023
        ]
        
        for fmt in date_formats:
            try:
                from datetime import datetime
                return datetime.strptime(date_str.strip(), fmt).date()  # Return date object, not string
            except:
                continue
        return None

    def _clean_number(self, value):
        """Clean and parse numeric values"""
        if not value or str(value).strip() == '':
            return 0.0
        
        # Convert to string
        cleaned = str(value).strip()
        
        # Handle negative numbers in parentheses: (1000) -> -1000
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        
        # Remove common formatting characters
        cleaned = cleaned.replace(',', '').replace(' ', '').replace('\xa0', '')
        
        # Remove currency symbols (including unicode variants)
        for symbol in ['$', '€', '£', 'RM', 'USD', 'EUR', 'GBP', '₹', '¥', 'â‚¬', 'Â£']:
            cleaned = cleaned.replace(symbol, '')
        
        # Remove any remaining non-numeric characters except minus and decimal point
        cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')
        
        # Handle multiple decimal points (keep only first)
        if cleaned.count('.') > 1:
            parts = cleaned.split('.')
            cleaned = parts[0] + '.' + ''.join(parts[1:])
        
        # Handle multiple minus signs (keep only first if at start)
        if cleaned.count('-') > 1:
            cleaned = '-' + cleaned.replace('-', '')
        elif '-' in cleaned and not cleaned.startswith('-'):
            cleaned = cleaned.replace('-', '')
        
        try:
            result = float(cleaned) if cleaned and cleaned != '-' else 0.0
            # For PO amounts, negative values should be treated as 0
            return max(0.0, result)
        except (ValueError, TypeError):
            return 0.0


class POBalanceNotification(models.Model):
    """Notifications for PO balance thresholds"""
    
    THRESHOLD_CHOICES = [
        (50, '50% Used'),
        (75, '75% Used'), 
        (90, '90% Used - Low Balance'),
    ]
    
    purchase_order = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.CASCADE, 
        related_name='balance_notifications'
    )
    threshold_percentage = models.IntegerField(choices=THRESHOLD_CHOICES)
    utilization_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['purchase_order', 'threshold_percentage']
        verbose_name = 'PO Balance Notification'
        verbose_name_plural = 'PO Balance Notifications'
    
    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.threshold_percentage}% threshold"
    
    @property
    def message(self):
        """Generate notification message"""
        if self.threshold_percentage == 90:
            return f"⚠️ Critical: PO {self.purchase_order.po_number} is at {self.utilization_percentage}% utilization (Low Balance)"
        elif self.threshold_percentage == 75:
            return f"⚡ Warning: PO {self.purchase_order.po_number} is at {self.utilization_percentage}% utilization"
        else:
            return f"ℹ️ Notice: PO {self.purchase_order.po_number} is at {self.utilization_percentage}% utilization"
    
    @property
    def priority_class(self):
        """Get priority class for styling"""
        if self.threshold_percentage == 90:
            return 'critical'
        elif self.threshold_percentage == 75:
            return 'warning' 
        else:
            return 'info'


class PurchaseOrderAttachment(models.Model):
    """File attachments for purchase orders"""
    
    purchase_order = models.ForeignKey(
        PurchaseOrder, 
        related_name='attachments', 
        on_delete=models.CASCADE
    )
    file = models.FileField(upload_to='purchase_orders/attachments/')
    original_filename = models.CharField(max_length=255)
    description = models.CharField(max_length=500, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Purchase Order Attachment'
        verbose_name_plural = 'Purchase Order Attachments'
    
    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.original_filename}"


class PurchaseOrderChangeLog(models.Model):
    """Track changes to purchase orders"""
    
    purchase_order = models.ForeignKey(
        PurchaseOrder, 
        related_name='change_logs', 
        on_delete=models.CASCADE
    )
    field_changed = models.CharField(max_length=50)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'Purchase Order Change Log'
        verbose_name_plural = 'Purchase Order Change Logs'
    
    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.field_changed} changed"