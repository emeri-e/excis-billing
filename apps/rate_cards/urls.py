from django.urls import path
from . import views

app_name = 'rate_cards'

urlpatterns = [
    path('', views.rate_card_list, name='list'),
    path('create/', views.create_rate_card, name='create'),
]