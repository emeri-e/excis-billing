from django.urls import path
from . import views

app_name = 'purchase_orders'

urlpatterns = [
    # Main purchase order pages
    path('', views.purchase_order_list, name='list'),
    path('create/', views.create_purchase_order, name='create'),
    path('<int:pk>/', views.purchase_order_detail, name='detail'),
    path('<int:pk>/edit/', views.edit_purchase_order, name='edit'),
    path('<int:pk>/delete/', views.delete_purchase_order, name='delete'),
    
    # Export functionality
    path('export/', views.export_purchase_orders, name='export'),
    
    # API endpoints for AJAX functionality
    path('api/<int:pk>/', views.get_purchase_order_api, name='po_detail_api'),
    path('api/<int:pk>/duplicate/', views.duplicate_purchase_order_api, name='duplicate_po_api'),
    path('api/<int:pk>/delete/', views.delete_purchase_order_api, name='delete_po_api'),
    path('api/customers/<int:customer_id>/accounts/', views.get_customer_accounts_for_po, name='customer_accounts_for_po'),
    
    # Notification API endpoints
    path('api/notifications/', views.get_notifications_api, name='get_notifications'),
    path('api/notifications/<int:notification_id>/read/', views.mark_notification_read_api, name='mark_notification_read'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read_api, name='mark_all_notifications_read'),
    path('test-notifications/', views.test_notification_system, name='test_notifications'),
    path('clear-pdf-data/', views.clear_pdf_data, name='clear_pdf_data'),
    path('debug-pdf/', views.debug_pdf_extraction, name='debug_pdf'),
]