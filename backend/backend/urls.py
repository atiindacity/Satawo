from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/funds/', include('funds.urls')),
    path('api/stores/', include('stores.urls')),
    path('', TemplateView.as_view(template_name="index.html")),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
