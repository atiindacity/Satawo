from rest_framework import serializers
from .models import User
class UserSerializer(serializers.ModelSerializer):
    address = serializers.CharField(write_only=True, required=False)
    class Meta:
        model = User
        fields = ['id','username','full_name','phone','email','role','profile_photo','license_photo','address','is_active']
    def create(self, validated_data):
        addr = validated_data.pop('address', None)
        user = super().create(validated_data)
        user.set_address(addr or '')
        user.set_password(validated_data.get('password','password123'))
        user.save()
        return user
