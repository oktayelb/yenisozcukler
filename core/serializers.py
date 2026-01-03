from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Word, Comment
import re
import requests
from decouple import config
# --- OKUMA (READ) SERIALIZERS ---

class CommentSerializer(serializers.ModelSerializer):
    score = serializers.IntegerField(read_only=True)
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'word', 'author', 'comment', 'timestamp', 'score', 'user_vote']

    def get_user_vote(self, obj):
        votes = self.context.get('user_votes', {})
        vote_value = votes.get(obj.id)
        
        if vote_value == 1: return 'like'
        if vote_value == -1: return 'dislike'
        return None

class WordSerializer(serializers.ModelSerializer):
    score = serializers.IntegerField(read_only=True)
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Word
        fields = ['id', 'word', 'author', 'score', 'timestamp', 'user_vote', 'is_profane', 'definition'] 

    def get_user_vote(self, obj):
        votes = self.context.get('user_votes', {})
        vote_value = votes.get(obj.id)
        
        if vote_value == 1: return 'like'
        if vote_value == -1: return 'dislike'
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['def'] = instance.definition 
        return data

# --- YAZMA (WRITE) SERIALIZERS ---

class WordCreateSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(source='author', required=False, allow_blank=True, max_length=50)
    
    class Meta:
        model = Word
        fields = ['word', 'definition', 'nickname', 'is_profane']

    def validate_word(self, value):
        value = value.strip()
        if not re.match(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()-]+$', value):
            raise serializers.ValidationError("Sözcük sadece harf, rakam ve temel noktalama işaretleri içerebilir.")
        return value

    def validate_definition(self, value):
        value = value.strip()
        if not re.match(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()-]+$', value):
            raise serializers.ValidationError("Tanım geçersiz karakterler içeriyor.")
        return value

    def validate_nickname(self, value):
        if not value or not value.strip():
            return "Anonim"
        if value:
            value = value.strip()
            if not re.match(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()-]*$', value):
                raise serializers.ValidationError("Takma ad geçersiz karakterler içeriyor.")
        return value 

class CommentCreateSerializer(serializers.ModelSerializer):
    word_id = serializers.IntegerField()
    
    class Meta:
        model = Comment
        fields = ['word_id', 'author', 'comment']
        extra_kwargs = {
            'author': {'required': False, 'allow_blank': True}
        }

    def validate_comment(self, value):
        value = value.strip()
        if len(value) > 200:
            raise serializers.ValidationError("Yorum 200 karakteri geçemez.")
        if not value:
            raise serializers.ValidationError("Yorum boş olamaz.")
        return value

    def validate_author(self, value):
        return value.strip() if value else "Anonim"
    

class AuthSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=20)
    password = serializers.CharField(min_length=6, write_only=True)
    token = serializers.CharField(write_only=True, required=True) # Yeni alan
    def validate_username(self, value):
        value = value.strip()

        if value.lower() == 'anonim':
            raise serializers.ValidationError("Bu kullanıcı adı sistem tarafından ayrılmıştır, alınamaz.")
        
        if not re.match(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()-]*$', value):
            raise serializers.ValidationError("Kullanıcı adı sadece harf, rakam ve '_' içerebilir.")
        return value
    
    def validate(self, attrs):
        token = attrs.get('token')
        
        # Cloudflare Verify API
        secret_key = config('CLOUDFLARE_SECRET_KEY')
        verify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        
        data = {
            'secret': secret_key,
            'response': token
        }
        
        try:
            response = requests.post(verify_url, data=data)
            result = response.json()
            
            if not result.get('success'):
                raise serializers.ValidationError({"token": "Robot doğrulaması başarısız oldu. Lütfen tekrar deneyin."})
                
        except requests.RequestException:
             raise serializers.ValidationError({"token": "Doğrulama sunucusuna ulaşılamadı."})

        return attrs

# --- YENİ EKLENEN SERIALIZER ---
class ChangeUsernameSerializer(serializers.Serializer):
    new_username = serializers.CharField(max_length=20, required=True)

    def validate_new_username(self, value):
        value = value.strip()
        # View'dan context ile gönderilen request'ten user'ı alıyoruz
        user = self.context['request'].user 

        # 1. Boşluk kontrolü
        if not value:
            raise serializers.ValidationError("Kullanıcı adı boş olamaz.")

        # 2. Yasaklı kelime kontrolü
        if value.lower() == 'anonim':
            raise serializers.ValidationError("Bu kullanıcı adı sistem tarafından ayrılmıştır.")

        # 3. Regex (Karakter) kontrolü (AuthSerializer ile aynı)
        if not re.match(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()-]*$', value):
            raise serializers.ValidationError("Kullanıcı adı geçersiz karakterler içeriyor.")

        # 4. Müsaitlik kontrolü (Kendisi hariç başkası almış mı?)
        if User.objects.filter(username__iexact=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Bu kullanıcı adı zaten kullanımda.")

        return value    