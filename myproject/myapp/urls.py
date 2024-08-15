# myapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.test_api),
    path('stock_data/<str:stock_id>/<str:timespan>/<str:time>', views.get_stock_data_api),
    path('news/<str:stock_id>', views.get_news_api),
    path('account/', views.get_account_api),
]