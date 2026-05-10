from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/', include('patients.urls')),
    path('api/', include('tasks.urls')),
    path('api/', include('reports.urls')),
    path('api/', include('master.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)