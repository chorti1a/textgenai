from django.urls import path
from apps.textai import views

urlpatterns = [
    path('', views.textai_view, name='textai'),  # /textai/
    path('auth/login/', views.bungie_login, name='bungie_login'),  # /textai/auth/login/
    path('auth/callback/', views.bungie_callback, name='bungie_callback'),
    path('auth/logout/', views.bungie_logout, name='bungie_logout'),
    path('auth/status/', views.auth_status, name='auth_status'),
]
