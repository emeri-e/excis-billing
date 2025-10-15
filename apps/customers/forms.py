import logging
from django import forms
from .models import Customer, Account, Project, BillingCycle, Currency, Country

logger = logging.getLogger('customers')

class CustomerForm(forms.ModelForm):
    # Project fields embedded in customer form
    project_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Name of the initial project for this customer'
    )
    project_code = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Short code for the project (e.g., PROJ1)'
    )
    project_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        help_text='Optional project description'
    )
    
    class Meta:
        model = Customer
        fields = ['name', 'code', 'email', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['customer', 'name', 'code', 'description']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)


class BillingCycleForm(forms.ModelForm):
    class Meta:
        model = BillingCycle
        fields = ['name', 'cycle_type', 'customer', 'account', 'project', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'cycle_type': forms.Select(attrs={'class': 'form-select'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'account': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)
        self.fields['customer'].required = False
        self.fields['account'].required = False
        self.fields['project'].required = False
        
        # If customer is set, filter projects
        if 'customer' in self.data:
            try:
                customer_id = int(self.data.get('customer'))
                self.fields['project'].queryset = Project.objects.filter(
                    customer_id=customer_id, is_active=True
                )
                self.fields['account'].queryset = Account.objects.filter(
                    customer_id=customer_id, is_active=True
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.customer:
            self.fields['project'].queryset = Project.objects.filter(
                customer=self.instance.customer, is_active=True
            )
            self.fields['account'].queryset = Account.objects.filter(
                customer=self.instance.customer, is_active=True
            )
        else:
            self.fields['project'].queryset = Project.objects.none()
            self.fields['account'].queryset = Account.objects.none()


class CurrencyForm(forms.ModelForm):
    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'USD',
                'maxlength': 3,
                'style': 'text-transform: uppercase;'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'US Dollar'
            }),
            'symbol': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '$'
            }),
        }


class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'United States'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'USA',
                'maxlength': 3,
                'style': 'text-transform: uppercase;'
            }),
        }


class AccountForm(forms.ModelForm):
    new_currency_code = forms.CharField(
        max_length=3,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., KES',
            'style': 'text-transform: uppercase;'
        }),
        help_text='Add new currency if not in list'
    )
    new_currency_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Kenyan Shilling'
        })
    )
    new_currency_symbol = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., KSh'
        })
    )
    new_country_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Kenya'
        }),
        help_text='Add new country if not in list'
    )
    new_country_code = forms.CharField(
        max_length=3,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., KEN',
            'maxlength': 3,
            'style': 'text-transform: uppercase;'
        })
    )
    
    class Meta:
        model = Account
        fields = [
            'customer', 'name', 'account_id', 'region', 'country',
            'billing_cycle', 'currency', 'contact_email', 'contact_phone', 'notes'
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_id': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., East Africa, EMEA, North America'
            }),
            'country': forms.Select(attrs={'class': 'form-select'}),
            'billing_cycle': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Basic queryset setup
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)
        self.fields['billing_cycle'].queryset = BillingCycle.objects.filter(is_active=True)
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
        self.fields['country'].queryset = Country.objects.filter(is_active=True)
        self.fields['currency'].required = False
        self.fields['country'].required = False


    def clean(self):
        cleaned_data = super().clean()
        logger.debug(f"Cleaning form data: {cleaned_data}")
        
        # Handle new currency
        new_curr_code = cleaned_data.get('new_currency_code')
        new_curr_name = cleaned_data.get('new_currency_name')
        currency = cleaned_data.get('currency')
        
        if new_curr_code and new_curr_name:
            currency, created = Currency.objects.get_or_create(
                code=new_curr_code.upper(),
                defaults={
                    'name': new_curr_name,
                    'symbol': cleaned_data.get('new_currency_symbol', '')
                }
            )
            cleaned_data['currency'] = currency
        elif not currency:
            raise forms.ValidationError('Please select a currency or add a new one')
        
        # Handle new country
        new_country_name = cleaned_data.get('new_country_name')
        new_country_code = cleaned_data.get('new_country_code')
        country = cleaned_data.get('country')
        
        if new_country_name and new_country_code:
            country, created = Country.objects.get_or_create(
                code=new_country_code.upper(),
                defaults={'name': new_country_name}
            )
            cleaned_data['country'] = country
        
        return cleaned_data