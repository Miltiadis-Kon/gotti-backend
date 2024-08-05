# myapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.test_api),
    path('stock_data', views.get_stock_data),
]