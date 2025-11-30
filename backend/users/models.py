from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils import timezone
from cryptography.fernet import Fernet, InvalidToken
import base64, os
# Custom user with role field and encrypted sensitive fields
ROLE_CHOICES = [
    ('admin','Admin'),('subadmin','SubAdmin'),('store','Store'),('collector','Collector'),('user','User')
]
def gen_random_filename(instance, filename):
    ext = filename.split('.')[-1]
    return f'uploads/{instance.username}/{os.urandom(8).hex()}.{ext}'
class User(AbstractUser):
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, validators=[RegexValidator(r'^\+?\d{7,15}$')])
    address_encrypted = models.BinaryField(null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    profile_photo = models.ImageField(upload_to=gen_random_filename, null=True, blank=True)
    license_photo = models.ImageField(upload_to=gen_random_filename, null=True, blank=True)
    # Example helper: encrypt/decrypt address
    def set_address(self, plaintext):
        key = settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY,str) else settings.FERNET_KEY
        f = Fernet(key)
        self.address_encrypted = f.encrypt(plaintext.encode())
    def get_address(self):
        if not self.address_encrypted:
            return ''
        key = settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY,str) else settings.FERNET_KEY
        f = Fernet(key)
        try:
            return f.decrypt(self.address_encrypted).decode()
        except InvalidToken:
            return 'ENCRYPTION_ERROR'
