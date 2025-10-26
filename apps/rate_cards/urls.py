from django.urls import path
from . import views

app_name = 'rate_cards'

urlpatterns = [
    path('', views.rate_card_list, name='list'),
    path('create/', views.create_rate_card, name='create'),
    # JSON endpoints for the front-end
    path('api/ratecards/', views.ratecard_list, name='ratecard_list'),            # GET -> list
    path('api/ratecards/create/', views.ratecard_create, name='ratecard_create'),# POST -> create
    path('api/ratecards/<int:pk>/', views.ratecard_detail, name='ratecard_detail'), # GET -> detail
    path('api/ratecards/<int:pk>/update/', views.ratecard_update, name='ratecard_update'), # POST -> update
    path('api/ratecards/<int:pk>/delete/', views.ratecard_delete, name='ratecard_delete'), # POST -> delete

    # service rates for a given ratecard
    path('api/ratecards/<int:pk>/service_rates/', views.service_rates_for_ratecard, name='service_rates'),
    path('api/service_rate/<int:pk>/update/', views.service_rate_update, name='service_rate_update'),
    path('api/service_rate/<int:pk>/delete/', views.service_rate_delete, name='service_rate_delete'),
    path('api/service_rate/create/', views.service_rate_create, name='service_rate_create'),
    path('api/ratecards/<int:pk>/<str:svc_type>s/', views.svc_list_for_ratecard, name='svc_list_for_ratecard'),
    path('api/<str:svc_type>/create/', views.svc_create, name='svc_create'),
    path('api/<str:svc_type>/<int:pk>/update/', views.svc_update, name='svc_update'),
    path('api/<str:svc_type>/<int:pk>/delete/', views.svc_delete, name='svc_delete'),
]

