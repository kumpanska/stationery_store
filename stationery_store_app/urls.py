"""
URL configuration for stationery_store_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/director/', views.director_login, name='director_login'),
    path('login/manager/', views.manager_login, name='manager_login'),
    path('login/seller/', views.seller_login, name='seller_login'),
    path('register/<str:role>/', views.register, name='register'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('director/panel', views.director_panel, name = 'director_panel'),

    path('admin/', admin.site.urls),
]
