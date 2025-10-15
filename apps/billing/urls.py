from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # Main billing run pages
    path('', views.billing_run_list, name='list'),
    path('create/', views.create_billing_run, name='create'),
    path('create-wizard/', views.create_billing_run_wizard, name='create_wizard'),
    
    # API endpoints for AJAX calls
    path('api/customers/<int:customer_id>/accounts/', views.get_customer_accounts_api, name='customer_accounts_api'),
    path('api/accounts/<int:account_id>/', views.get_account_details_api, name='account_details_api'),
]