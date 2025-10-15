from django import forms
from django.core.exceptions import ValidationError
from .models import PurchaseOrder, PurchaseOrderAttachment
from apps.customers.models import Customer, Account
import uuid
from datetime import date, timedelta
import logging

# Configure logger at the top of forms.py
logger = logging.getLogger(__name__)

class PurchaseOrderForm(forms.ModelForm):
    balance = forms.DecimalField(
        max_digits=15, 
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'step': '0.01',
            'placeholder': '0'
        }),
        help_text='Current balance/remaining amount',
        label='Balance'
    )

    reference_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'auto from customer (3 chars)'
        }),
        help_text='Reference number for this PO',
        label='Reference Number'
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            'customer', 'account', 'currency', 'total_amount', 'balance',
            'valid_from', 'valid_until', 'reference_number', 'notes', 'department', 'project_code',
            'items_description', 'delivery_terms', 'payment_terms', 
            'delivery_date',
        ]
        widgets = {
            'customer': forms.Select(attrs={
                'class': 'form-select',
            }),
            'account': forms.Select(attrs={
                'class': 'form-select',
            }),
            'total_amount': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01', 
                'placeholder': 'Enter total amount'
            }),
            'valid_from': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date', 
                'placeholder': 'YYYY-MM-DD'
            }),
            'valid_until': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date', 
                'placeholder': 'YYYY-MM-DD'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-select'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Optional notes about this purchase order'
            }),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., IT, Finance, Operations'}),
            'project_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Project identifier'}),
            'items_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description of purchased items/services'}),
            'delivery_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., FOB, CIF, EXW'}),
            'payment_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Net 30, 50% advance'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'customer': 'Customer',
            'account': 'Account', 
            'currency': 'Currency',
            'total_amount': 'Total',
            'valid_from': 'Valid From',
            'valid_until': 'Valid Until',
            'notes': 'Notes',
            'department': 'Department',
            'project_code': 'Project Code',
            'items_description': 'Items Description',
            'delivery_terms': 'Delivery Terms',
            'payment_terms': 'Payment Terms',
            'delivery_date': 'Delivery Date',
        }

    def __init__(self, *args, **kwargs):
        self.pdf_data = kwargs.pop('pdf_data', None)
        super().__init__(*args, **kwargs)
        # Auto-fill from PDF data if available
        if self.pdf_data:
            self.auto_fill_from_pdf()
        
        # Set up customer queryset with active customers only
        self.fields['customer'].queryset = Customer.objects.filter(
            is_active=True
        ).order_by('name')
        self.fields['customer'].empty_label = "Select customer"
        
        # Initialize account queryset
        customer = None
        if self.initial.get('customer'):  # Check initial data
            customer = self.initial['customer']
        elif self.data.get('customer'):  # Check submitted data
            try:
                customer = Customer.objects.get(pk=self.data['customer'], is_active=True)
            except (Customer.DoesNotExist, ValueError):
                pass
        elif self.instance.pk and self.instance.customer:  # Check instance for editing
            customer = self.instance.customer
        
        # Set account queryset based on customer
        if customer:
            self.fields['account'].queryset = Account.objects.filter(
                customer=customer, is_active=True
            ).order_by('name')
            self.fields['account'].empty_label = "No specific account"
        else:
            self.fields['account'].queryset = Account.objects.none()
            self.fields['account'].empty_label = "Select customer first"
        
        # Set initial values for editing
        if self.instance.pk and self.instance.customer:
            self.fields['balance'].initial = self.instance.remaining_balance
            if hasattr(self.instance, 'reference_number'):
                self.fields['reference_number'].initial = self.instance.reference_number
        
        # Set default dates for new PO
        if not self.instance.pk:
            today = date.today()
            next_year = today + timedelta(days=365)
            self.fields['valid_from'].initial = today
            self.fields['valid_until'].initial = next_year
            self.fields['balance'].initial = 0
        
        # Add help texts and required fields
        self.fields['customer'].help_text = 'Select the customer for this PO'
        self.fields['account'].help_text = 'Select specific account (optional)'
        self.fields['total_amount'].help_text = 'Total amount available for billing'
        self.fields['currency'].help_text = 'Currency for all amounts in this PO'
        self.fields['valid_from'].help_text = 'Start date for PO validity (can be historical)'
        self.fields['valid_until'].help_text = 'End date for PO validity (can be historical)'
        
        self.fields['customer'].required = True
        self.fields['total_amount'].required = True
        self.fields['valid_from'].required = True
        self.fields['valid_until'].required = True
        self.fields['currency'].required = True
        self.fields['department'].help_text = 'Department responsible for this purchase'
        self.fields['project_code'].help_text = 'Associated project code (if applicable)'
        self.fields['items_description'].help_text = 'Detailed description of items/services being purchased'
        self.fields['delivery_terms'].help_text = 'Terms of delivery (FOB, CIF, etc.)'
        self.fields['payment_terms'].help_text = 'Payment terms and conditions'
        self.fields['delivery_date'].help_text = 'Expected delivery date'
        

    def clean_customer(self):
        """Validate customer field"""
        customer = self.cleaned_data.get('customer')
        if not customer:
            raise ValidationError('Customer is required.')
        if not customer.is_active:
            raise ValidationError('Selected customer is not active.')
        return customer
    
    def clean_account(self):
        """Validate account field with dynamic queryset"""
        account = self.cleaned_data.get('account')
        logger.debug("clean_account: cleaned_data=%s, account_type=%s, account_value=%s", 
                    self.cleaned_data, type(account), account)
        
        # If no account selected, return None (optional field)
        if not account:
            return None
        
        # Validate account is active
        if not account.is_active:
            raise ValidationError('Selected account is not active.')
        
        # Ensure account belongs to the selected customer
        customer = self.cleaned_data.get('customer')
        if customer and account.customer != customer:
            raise ValidationError('Selected account must belong to the selected customer.')
        
        # If no customer selected but account is provided, that's invalid
        if not customer:
            raise ValidationError('You must select a customer before selecting an account.')
        
        return account
    
    def clean_total_amount(self):
        """Validate total amount"""
        total_amount = self.cleaned_data.get('total_amount')
        if total_amount is not None and total_amount <= 0:
            raise ValidationError('Total amount must be greater than 0.')
        return total_amount
    
    def clean_balance(self):
        """Validate balance field"""
        balance = self.cleaned_data.get('balance')
        if balance is not None and balance < 0:
            raise ValidationError('Balance cannot be negative.')
        return balance
    
    def clean_valid_from(self):
        """Validate valid from date - Allow historical dates"""
        valid_from = self.cleaned_data.get('valid_from')
        # Allow past dates for historical records
        # No validation needed - users can enter old PO data
        return valid_from
    
    def clean_valid_until(self):
        """Validate valid until date - Allow historical dates"""
        valid_until = self.cleaned_data.get('valid_until')
        # Allow past dates for historical records
        # The main validation is in clean() to ensure valid_until > valid_from
        return valid_until
    
    def clean_reference_number(self):
        """Clean and validate reference number"""
        reference_number = self.cleaned_data.get('reference_number', '').strip()
        
        # If empty, auto-generate from customer
        if not reference_number:
            customer = self.cleaned_data.get('customer')
            if customer:
                reference_number = self.generate_reference_number(customer)
        
        return reference_number
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        
        # Validate date range
        valid_from = cleaned_data.get('valid_from')
        valid_until = cleaned_data.get('valid_until')
        
        if valid_from and valid_until and valid_from >= valid_until:
            raise ValidationError({
                'valid_until': 'Valid until date must be after valid from date.'
            })
        
        # Validate balance against total amount
        total_amount = cleaned_data.get('total_amount')
        balance = cleaned_data.get('balance')
        
        if total_amount and balance and balance > total_amount:
            raise ValidationError({
                'balance': 'Balance cannot be greater than total amount.'
            })
        
        # If balance is not provided, set it to total amount for new POs
        if not self.instance.pk and total_amount and not balance:
            cleaned_data['balance'] = total_amount
        
        # Validate PO number uniqueness if provided
        po_number = self.generate_po_number(cleaned_data.get('customer'))
        if PurchaseOrder.objects.filter(po_number=po_number).exclude(pk=self.instance.pk).exists():
            # This will be handled in save method with auto-increment
            pass
        
        return cleaned_data
    
    def generate_reference_number(self, customer):
        """Generate reference number from customer"""
        if customer and customer.name:
            # Take first 3 characters of customer name, uppercase
            return customer.name[:3].upper()
        return 'REF'
    
    def generate_po_number(self, customer):
        """Generate a unique PO number"""
        if not customer:
            customer_code = 'PO'
        else:
            # Use customer name first 3 chars or customer code if available
            customer_code = getattr(customer, 'code', customer.name[:3]).upper()
        
        year = date.today().year
        random_suffix = str(uuid.uuid4())[:6].upper()
        
        return f"PO-{customer_code}-{year}-{random_suffix}"
    
    def save(self, commit=True):
        """Save the purchase order with proper field mapping"""
        instance = super().save(commit=False)
        
        # Map the balance field to remaining_balance
        balance = self.cleaned_data.get('balance')
        if balance is not None:
            instance.remaining_balance = balance
        elif not instance.pk:
            # For new POs, set remaining_balance to total_amount if balance not provided
            instance.remaining_balance = instance.total_amount
        
        # Set reference number from form
        reference_number = self.cleaned_data.get('reference_number')
        if reference_number:
            instance.reference_number = reference_number
        
        # Auto-generate PO number if not set
        if not instance.po_number:
            instance.po_number = self.generate_po_number(instance.customer)
            
            # Ensure uniqueness
            counter = 1
            original_po_number = instance.po_number
            while PurchaseOrder.objects.filter(po_number=instance.po_number).exclude(pk=instance.pk).exists():
                instance.po_number = f"{original_po_number}-{counter}"
                counter += 1
        
        if commit:
            instance.save()
        
        return instance

    def auto_fill_from_pdf(self):
        """Enhanced auto-fill specifically for this PO format"""
        if not self.pdf_data:
            logger.warning("auto_fill_from_pdf: No PDF data available")
            return
        
        logger.info(f"PDF data available with keys: {list(self.pdf_data.keys())}")
        
        # Set reference number (PO Number)
        if self.pdf_data.get('reference_number'):
            self.fields['reference_number'].initial = self.pdf_data['reference_number']
            logger.info(f"✓ Set reference_number: {self.pdf_data['reference_number']}")
        
        # Set currency (always MYR for this format)
        self.fields['currency'].initial = 'MYR'
        logger.info("✓ Set currency: MYR")
        
        # Set total amount
        if self.pdf_data.get('total_amount'):
            self.fields['total_amount'].initial = self.pdf_data['total_amount']
            logger.info(f"✓ Set total_amount: {self.pdf_data['total_amount']}")
        
        # Set balance (calculated from total - invoiced)
        if self.pdf_data.get('balance'):
            self.fields['balance'].initial = self.pdf_data['balance']
            logger.info(f"✓ Set balance: {self.pdf_data['balance']}")
        elif self.pdf_data.get('total_amount'):
            self.fields['balance'].initial = self.pdf_data['total_amount']
            logger.info(f"✓ Set balance = total_amount: {self.pdf_data['total_amount']}")
        
        # Set dates
        if self.pdf_data.get('valid_from'):
            self.fields['valid_from'].initial = self.pdf_data['valid_from']
            logger.info(f"✓ Set valid_from: {self.pdf_data['valid_from']}")
        
        if self.pdf_data.get('valid_until'):
            self.fields['valid_until'].initial = self.pdf_data['valid_until']
            logger.info(f"✓ Set valid_until: {self.pdf_data['valid_until']}")
        
        # Set customer if matched
        if self.pdf_data.get('matched_customer_id'):
            self.fields['customer'].initial = self.pdf_data['matched_customer_id']
            logger.info(f"✓ Set customer: {self.pdf_data['matched_customer_id']}")
        
        # Build comprehensive notes
        notes_parts = []
        
        # Add supplier information
        if self.pdf_data.get('supplier'):
            notes_parts.append(f"Supplier: {self.pdf_data['supplier']}")
        
        if self.pdf_data.get('from_company'):
            notes_parts.append(f"Buyer: {self.pdf_data['from_company']}")
        
        # Add description
        if self.pdf_data.get('description'):
            notes_parts.append(f"Description: {self.pdf_data['description']}")
            # Also set items_description field if it exists
            if hasattr(self, 'fields') and 'items_description' in self.fields:
                self.fields['items_description'].initial = self.pdf_data['description']
        
        # Add financial summary
        currency = self.pdf_data.get('currency', 'MYR')
        
        if self.pdf_data.get('total_amount'):
            notes_parts.append(f"Subtotal: {currency} {self.pdf_data['total_amount']:,.2f}")
        
        if self.pdf_data.get('total_tax'):
            notes_parts.append(f"Tax: {currency} {self.pdf_data['total_tax']:,.2f}")
        
        if self.pdf_data.get('grand_total'):
            notes_parts.append(f"Grand Total: {currency} {self.pdf_data['grand_total']:,.2f}")
        
        if self.pdf_data.get('total_invoiced'):
            notes_parts.append(f"Invoiced to Date: {currency} {self.pdf_data['total_invoiced']:,.2f}")
        
        # Add additional information
        if self.pdf_data.get('payment_terms'):
            notes_parts.append(f"Payment Terms: {self.pdf_data['payment_terms']}")
            # Also set payment_terms field if it exists
            if hasattr(self, 'fields') and 'payment_terms' in self.fields:
                self.fields['payment_terms'].initial = self.pdf_data['payment_terms']
        
        if self.pdf_data.get('requester'):
            notes_parts.append(f"Requester: {self.pdf_data['requester']}")
        
        if self.pdf_data.get('billing_frequency'):
            notes_parts.append(f"Billing Frequency: {self.pdf_data['billing_frequency']}")
        
        if self.pdf_data.get('quantity'):
            notes_parts.append(f"Quantity: {self.pdf_data['quantity']}")
        
        
        # Set notes
        if notes_parts:
            notes_content = '\n'.join(notes_parts)
            self.fields['notes'].initial = notes_content
            logger.info(f"✓ Set notes with {len(notes_parts)} items")
        
        logger.info("✓ Auto-fill from PDF completed successfully")
                

class PurchaseOrderEditForm(PurchaseOrderForm):
    """Specialized form for editing purchase orders with enhanced balance handling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance.pk:
            # Add additional context for editing
            original_balance = self.instance.remaining_balance
            total_amount = self.instance.total_amount
            used_amount = total_amount - original_balance
            
            # Update help texts with current PO info
            self.fields['balance'].help_text = (
                f'Current remaining: {original_balance}. '
                f'Used so far: {used_amount}. '
                f'Total authorized: {total_amount}'
            )
            
            # Add utilization percentage to total amount help text
            utilization = (used_amount / total_amount * 100) if total_amount > 0 else 0
            self.fields['total_amount'].help_text = (
                f'Currently {utilization:.1f}% utilized. '
                f'Changing this affects available balance.'
            )
    
    def clean(self):
        """Enhanced validation for edit form"""
        cleaned_data = super().clean()
        
        if self.instance.pk:
            total_amount = cleaned_data.get('total_amount')
            balance = cleaned_data.get('balance')
            
            # Calculate what the used amount would be
            if total_amount and balance is not None:
                used_amount = total_amount - balance
                
                # Warn if used amount would be negative (balance > total)
                if used_amount < 0:
                    raise ValidationError({
                        'balance': 'Balance cannot exceed total amount.'
                    })
                
                # If total amount is being reduced, ensure it's not less than used amount
                original_used = self.instance.total_amount - self.instance.remaining_balance
                if total_amount < original_used:
                    raise ValidationError({
                        'total_amount': f'Total amount cannot be reduced below the already used amount ({original_used}).'
                    })
        
        return cleaned_data

class PurchaseOrderAttachmentForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderAttachment
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].help_text = 'Brief description of the attached file'

class PurchaseOrderFilterForm(forms.Form):
    """Form for filtering purchase orders"""
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label='All Customers',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_active=True).select_related('customer').order_by('customer__name', 'name'),
        required=False,
        empty_label='All Accounts',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + PurchaseOrder.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    currency = forms.ChoiceField(
        choices=[('', 'All Currencies')] + [
            ('USD', 'US Dollar'),
            ('EUR', 'Euro'),
            ('GBP', 'British Pound'),
            ('CAD', 'Canadian Dollar'),
            ('AUD', 'Australian Dollar'),
            ('THB', 'Thai Baht'),
            ('MYR', 'Malaysian Ringgit')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search PO numbers...'
        })
    )

class BulkPurchaseOrderActionForm(forms.Form):
    """Form for bulk actions on purchase orders"""
    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('activate', 'Activate Selected'),
        ('expire', 'Mark as Expired'),
        ('export', 'Export Selected'),
        ('delete', 'Delete Selected'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    selected_pos = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    def clean_selected_pos(self):
        """Validate and parse selected PO IDs"""
        selected = self.cleaned_data.get('selected_pos', '')
        if not selected:
            raise forms.ValidationError('No purchase orders selected.')
        
        try:
            po_ids = [int(id.strip()) for id in selected.split(',') if id.strip()]
            if not po_ids:
                raise forms.ValidationError('No valid purchase order IDs provided.')
            return po_ids
        except ValueError:
            raise forms.ValidationError('Invalid purchase order IDs provided.')

class QuickPOCreateForm(forms.Form):
    """Simplified form for quick PO creation"""
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    total_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    currency = forms.ChoiceField(
        choices=[
            ('USD', 'US Dollar'),
            ('EUR', 'Euro'),
            ('GBP', 'British Pound'),
        ],
        initial='USD',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    duration_months = forms.IntegerField(
        initial=12,
        min_value=1,
        max_value=60,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text='PO validity period in months'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(is_active=True).order_by('name')
    
    def save(self, user):
        """Create a new PO from the form data"""
        from datetime import date, timedelta
        import uuid
        
        customer = self.cleaned_data['customer']
        account = self.cleaned_data.get('account')
        total_amount = self.cleaned_data['total_amount']
        currency = self.cleaned_data['currency']
        duration_months = self.cleaned_data['duration_months']
        
        # Generate PO number
        customer_code = customer.code[:3].upper()
        year = date.today().year
        random_suffix = str(uuid.uuid4())[:8].upper()
        po_number = f"PO-{customer_code}-{year}-{random_suffix}"
        
        # Calculate validity dates
        valid_from = date.today()
        valid_until = valid_from + timedelta(days=duration_months * 30)
        
        return PurchaseOrder.objects.create(
            po_number=po_number,
            customer=customer,
            account=account,
            total_amount=total_amount,
            remaining_balance=total_amount,
            valid_from=valid_from,
            valid_until=valid_until,
            currency=currency,
            created_by=user,
            status='active'
        )


class PurchaseOrderPDFUploadForm(forms.Form):
    pdf_file = forms.FileField(
        label='Upload Purchase Order PDF',
        help_text='Upload a PDF file to automatically extract PO details',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf'
        })
    )
    
    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get('pdf_file')
        if pdf_file:
            if not pdf_file.name.lower().endswith('.pdf'):
                raise ValidationError('Only PDF files are allowed.')
            if pdf_file.size > 10 * 1024 * 1024:  # 10MB limit
                raise ValidationError('File size must be less than 10MB.')
        return pdf_file