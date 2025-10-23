from django.urls import path
from . import views

app_name = 'purchase_orders'

urlpatterns = [
    # Main pages
    path('', views.purchase_order_list, name='list'),
   
    # CSV Upload
    path('upload-csv/', views.upload_csv, name='upload_csv'),
    path('bulk-create-from-csv/', views.bulk_create_pos_from_csv, name='bulk_create_from_csv'),
   
    # API endpoints
    path('api/create/', views.create_purchase_order_api, name='create_po_api'),
    path('api/<int:pk>/', views.get_purchase_order_api, name='get_po_api'),
    path('api/<int:pk>/update/', views.update_purchase_order_api, name='update_po_api'),
    path('api/<int:pk>/delete/', views.delete_purchase_order_api, name='delete_po_api'),
   
    # Export
    path('export/', views.export_purchase_orders, name='export'),
   
    # Notifications
    path('api/notifications/', views.get_notifications_api, name='get_notifications'),
    path('api/notifications/<int:notification_id>/read/', views.mark_notification_read_api, name='mark_notification_read'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read_api, name='mark_all_notifications_read'),
]