
# funds/urls.py
from django.urls import path
from .views import deposit_view, transfer_view

urlpatterns = [
    path('deposit/', deposit_view, name='funds-deposit'),
    path('transfer/', transfer_view, name='funds-transfer'),
]
