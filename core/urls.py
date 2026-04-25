from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('textai/', include('apps.textai.urls')),
    path('', RedirectView.as_view(url='/textai/')),  # редирект с главной на /textai/
]
