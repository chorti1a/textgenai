from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='textai_index'),
    path('raid-checker/', views.raid_duality_check, name='raid_duality_check'),
]
