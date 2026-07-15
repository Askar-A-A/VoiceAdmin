from django.urls import path
from django.contrib.auth.views import LoginView
from .forms import LoginForm
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(template_name='accounts/login.html', authentication_form=LoginForm), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('settings/', views.account_settings, name='account_settings'),
]
