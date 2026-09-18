# accounts/serializers.py
"""Kayıt / giriş ve kullanıcı adı değiştirme doğrulaması."""

from rest_framework import serializers
from django.contrib.auth.models import User

from common.text import clean_username


class AuthSerializer(serializers.Serializer):
    # Turnstile verification is handled by the view (verify_turnstile) before the
    # serializer runs. Verifying here too would consume the single-use token a
    # second time and fail with `timeout-or-duplicate`.
    username = serializers.CharField(max_length=30)
    password = serializers.CharField(min_length=6, max_length=60, write_only=True)

    def validate_username(self, value):
        value = clean_username(value)

        if value == 'anonim':
            raise serializers.ValidationError("Bu kullanıcı adı sistem tarafından ayrılmıştır, alınamaz.")

        return value

class ChangeUsernameSerializer(serializers.Serializer):
    new_username = serializers.CharField(max_length=30, required=True)

    def validate_new_username(self, value):
        value = clean_username(value)
        user = self.context['request'].user

        if value in ['anonim', 'admin', 'moderator']:
            raise serializers.ValidationError("Bu kullanıcı adı sistem tarafından ayrılmıştır.")

        if User.objects.filter(username=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Bu kullanıcı adı zaten kullanımda.")

        return value
