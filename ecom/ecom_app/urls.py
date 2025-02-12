
from django.urls import path
from ecom_app import views

urlpatterns = [
    path('', views.home, name='home')
]