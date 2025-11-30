from django.db import models
from django.conf import settings
from django.utils import timezone
class Store(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    authorized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
