from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('textai/', include('apps.textai.urls')),  # существующие пути textai
    path('duality/', include('apps.textai.urls')),  # дублируем для короткого URL
]
