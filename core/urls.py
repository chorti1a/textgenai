from django.urls import path, include

urlpatterns = [
    # ... другие пути ...
    path('duality/', include('apps.textai.urls')),
]
