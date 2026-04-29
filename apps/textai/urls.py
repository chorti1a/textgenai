from django.urls import path
from . import views

urlpatterns = [
    path('', views.raid_duality_tracker, name='raid_duality_tracker'),
    path('api/check/', views.raid_duality_check, name='raid_duality_check'),
    # Если есть другие пути textai
    # path('analyze/', views.analyze, name='textai_analyze'),
]
