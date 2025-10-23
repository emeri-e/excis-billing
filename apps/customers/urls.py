from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    # Main customer & accounts management page
    path('accounts/', views.customer_accounts_list, name='accounts_list'),
    path('api/<int:customer_id>/accounts/', views.get_customer_accounts_api, name='customer_accounts_api'),
    
    # Traditional customer management
    path('', views.customer_list, name='list'),
    path('create/', views.create_customer, name='create'),
    path('<int:pk>/', views.customer_detail, name='detail'),
    path('<int:pk>/edit/', views.edit_customer, name='edit'),
    path('<int:pk>/delete/', views.delete_customer, name='delete'),
    
    # Account management
    path('accounts/create/', views.create_account, name='create_account'),
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),
    
    # AJAX endpoints
    path('ajax/load-projects/', views.load_projects, name='ajax_load_projects'),
    path('ajax/load-accounts/', views.load_accounts, name='ajax_load_accounts'),
    
    # Billing cycle management
    path('billing-cycles/', views.billing_cycles_list, name='billing_cycles_list'),
    path('billing-cycles/create/', views.create_billing_cycle, name='create_billing_cycle'),
    
    # Currency and Country management
    path('currencies/', views.manage_currencies, name='manage_currencies'),
    path('countries/', views.manage_countries, name='manage_countries'),

]