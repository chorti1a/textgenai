from django.contrib import admin
from django.urls import path, include
from apps.textai import views

urlpatterns = [
    path('', views.raid_duality_tracker, name='home'),
    path('api/check/', views.raid_duality_check, name='api_check'),
    path('admin/', admin.site.urls),
    path('textai/', include('apps.textai.urls')),
    path('duality/', include('apps.textai.urls')),
]
