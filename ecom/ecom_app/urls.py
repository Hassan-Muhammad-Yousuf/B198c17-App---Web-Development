from django.urls import path
from ecom_app import views

urlpatterns = [
    path('', views.home, name='home'),
    path('purchase', views.purchase, name='purchase'),
    path('tracker',views.tracker, name = "TrackingStatus"),
    path('checkout', views.checkout, name='Checkout'),
    path('success/', views.payment_success, name='payment_success'),
    path('cancel/', views.payment_cancel, name='payment_cancel'),
]
