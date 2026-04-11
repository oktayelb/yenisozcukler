from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Word, Comment, Category, Notification
import re
import requests
from decouple import config

# --- YARDIMCI FONKSİYONLAR (HELPER FUNCTIONS) ---

def validate_example_text(value):
    """Ortak örnek cümle doğrulama mantığı"""
    value = value.strip()
    if not value:
        raise serializers.ValidationError("Örnek cümle boş olamaz.")
    if len(value) > 200:
         raise serializers.ValidationError("Örnek cümle 200 karakteri geçemez.")
    
    # Inverted regex: matches anything that is NOT in the allowed set
    invalid_chars = set(re.findall(r'[^a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()\'"?!:;\-+?#]', value))
    if invalid_chars:
        raise serializers.ValidationError(f"Örnek cümlede geçersiz karakterler bulundu: {' '.join(invalid_chars)}")
        
    return value


# --- OKUMA (READ) SERIALIZERS ---

class NotificationSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, allow_null=True, default=None)
    word_text = serializers.CharField(source='word.word', read_only=True, allow_null=True, default=None)
    word_def = serializers.CharField(source='word.definition', read_only=True, allow_null=True, default=None)
    word_example = serializers.CharField(source='word.example', read_only=True, allow_null=True, default=None)
    word_etymology = serializers.CharField(source='word.etymology', read_only=True, allow_null=True, default=None)

    # Challenge-comment notifications (challenge_like / challenge_dislike)
    challenge_comment_id = serializers.IntegerField(read_only=True, allow_null=True)
    challenge_id = serializers.SerializerMethodField()
    challenge_foreign_word = serializers.SerializerMethodField()
    challenge_meaning = serializers.SerializerMethodField()
    challenge_timer_on = serializers.SerializerMethodField()
    challenge_is_closed = serializers.SerializerMethodField()
    challenge_time_remaining_seconds = serializers.SerializerMethodField()
    challenge_suggested_word = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'actor_username',
            'word_text', 'word_def', 'word_example', 'word_etymology',
            'message', 'is_read', 'timestamp', 'word_id', 'comment_id',
            'challenge_comment_id', 'challenge_id', 'challenge_foreign_word',
            'challenge_meaning', 'challenge_timer_on', 'challenge_is_closed',
            'challenge_time_remaining_seconds', 'challenge_suggested_word',
        ]

    def _challenge(self, obj):
        cc = getattr(obj, 'challenge_comment', None)
        return cc.challenge if cc else None

    def get_challenge_id(self, obj):
        ch = self._challenge(obj)
        return ch.id if ch else None

    def get_challenge_foreign_word(self, obj):
        ch = self._challenge(obj)
        return ch.foreign_word if ch else None

    def get_challenge_meaning(self, obj):
        ch = self._challenge(obj)
        return ch.meaning if ch else None

    def get_challenge_timer_on(self, obj):
        ch = self._challenge(obj)
        return ch.timer_on if ch else None

    def get_challenge_is_closed(self, obj):
        ch = self._challenge(obj)
        return ch.is_closed if ch else None

    def get_challenge_time_remaining_seconds(self, obj):
        ch = self._challenge(obj)
        if ch is None:
            return None
        remaining = ch.time_remaining
        if remaining is not None:
            return int(remaining.total_seconds())
        return None

    def get_challenge_suggested_word(self, obj):
        cc = getattr(obj, 'challenge_comment', None)
        return cc.suggested_word if cc else None


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description']

class CommentSerializer(serializers.ModelSerializer):
    score = serializers.IntegerField(read_only=True)
    user_vote = serializers.SerializerMethodField()
    author = serializers.CharField(source='display_author', read_only=True)

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
    comment_count = serializers.IntegerField(read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    author = serializers.CharField(source='display_author', read_only=True)

    class Meta:
        model = Word
        fields = ['id', 'word', 'slug', 'author', 'score', 'timestamp', 'user_vote', 'definition', 'example', 'etymology', 'comment_count', 'categories']

    def get_user_vote(self, obj):
        votes = self.context.get('user_votes', {})
        vote_value = votes.get(obj.id)
        
        if vote_value == 1: return 'like'
        if vote_value == -1: return 'dislike'
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Pop removes the original 'definition' key and assigns its value to 'def'
        data['def'] = data.pop('definition', None) 
        return data

# --- YAZMA (WRITE) SERIALIZERS ---

class WordAddExampleSerializer(serializers.Serializer):
    word_id = serializers.IntegerField(required=True)
    example = serializers.CharField(max_length=200, required=True)

    def validate_example(self, value):
        return validate_example_text(value)

class WordCreateSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(source='author', required=False, allow_blank=True, max_length=50)
    category_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=Category.objects.filter(is_active=True), 
        required=False, 
        write_only=True
    )
    
    class Meta:
        model = Word
        fields = ['word', 'definition', 'example', 'etymology', 'nickname', 'category_ids']

    def create(self, validated_data):
        categories = validated_data.pop('category_ids', [])
        word = Word.objects.create(**validated_data)
        
        if categories:
            word.categories.set(categories)
            
        return word

    def turkish_lower(self, text):
        if not text:
            return ""
        return text.replace('I', 'ı').replace('İ', 'i').lower()

    def validate_word(self, value):
        value = value.strip()
        invalid_chars = set(re.findall(r'[^a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()\-]', value))
        if invalid_chars:
            raise serializers.ValidationError(f"Sözcükte geçersiz karakterler bulundu: {' '.join(invalid_chars)}")
        return self.turkish_lower(value)

    def validate_definition(self, value):
        value = value.strip()
        # Apostrophe added to the allowed inverted set
        invalid_chars = set(re.findall(r'[^a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.;:,0-9()\-+?#\']', value))
        if invalid_chars:
            raise serializers.ValidationError(f"Tanımda geçersiz karakterler bulundu: {' '.join(invalid_chars)}")
        return self.turkish_lower(value)

    def validate_example(self, value):
        return validate_example_text(value)
        
    def validate_etymology(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Köken bilgisi boş olamaz.")
        
        value = value.strip()
        if len(value) > 200:
            raise serializers.ValidationError("Köken bilgisi 200 karakteri geçemez.")
            
        invalid_chars = set(re.findall(r'[^a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.;:,0-9()\-+?#\']', value))
        if invalid_chars:
            raise serializers.ValidationError(f"Köken bilgisinde geçersiz karakterler bulundu: {' '.join(invalid_chars)}")
        return value

    def validate_nickname(self, value):
        if not value or not value.strip():
            return "Anonim"

        value = value.strip()
        invalid_chars = set(re.findall(r'[^a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.,0-9()\-]', value))
        if invalid_chars:
            raise serializers.ValidationError(f"Takma adda geçersiz karakterler bulundu: {' '.join(invalid_chars)}")

        request = self.context.get('request')
        if not (request and request.user.is_authenticated) and User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Bu takma ad bir kullanıcı adı olarak alınmış, başka bir takma ad seçin.")

        return value

class CommentCreateSerializer(serializers.ModelSerializer):
    word_id = serializers.IntegerField()

    class Meta:
        model = Comment
        fields = ['word_id', 'comment']

    def validate_comment(self, value):
        value = value.strip()
        if len(value) > 200:
            raise serializers.ValidationError("Yorum 200 karakteri geçemez.")
        if not value:
            raise serializers.ValidationError("Yorum boş olamaz.")
        invalid_chars = set(re.findall(r'[^a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ\s.;:,0-9()\'"?!\-+#]', value))
        if invalid_chars:
            raise serializers.ValidationError(f"Yorumda geçersiz karakterler bulundu: {' '.join(invalid_chars)}")
        return value
    

class AuthSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30)
    password = serializers.CharField(min_length=6, max_length=60, write_only=True)
    token = serializers.CharField(write_only=True, required=True)
    
    def validate_username(self, value):
        value = value.strip()

        if value.lower() == 'anonim':
            raise serializers.ValidationError("Bu kullanıcı adı sistem tarafından ayrılmıştır, alınamaz.")
        
        invalid_chars = set(re.findall(r'[^a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ0-9_]', value))
        if invalid_chars:
            raise serializers.ValidationError(f"Kullanıcı adında geçersiz karakterler bulundu: {' '.join(invalid_chars)}")
            
        return value

    def validate(self, attrs):
        token = attrs.get('token')
        
        secret_key = config('CLOUDFLARE_SECRET_KEY')
        verify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        
        data = {
            'secret': secret_key,
            'response': token
        }
        
        try:
            # P7 Fix: Reduced timeout from 5 to 2.0 seconds to prevent worker exhaustion
            response = requests.post(verify_url, data=data, timeout=2.0)
            result = response.json()
            
            if not result.get('success'):
                raise serializers.ValidationError({"token": "Robot doğrulaması başarısız oldu. Lütfen tekrar deneyin."})
                
        except requests.RequestException:
             raise serializers.ValidationError({"token": "Doğrulama sunucusuna ulaşılamadı. Lütfen internet bağlantınızı kontrol edin."})

        return attrs

class ChangeUsernameSerializer(serializers.Serializer):
    new_username = serializers.CharField(max_length=30, required=True)

    def validate_new_username(self, value):
        value = value.strip()
        user = self.context['request'].user

        if not value:
            raise serializers.ValidationError("Kullanıcı adı boş olamaz.")

        if value.lower() in ['anonim', 'admin', 'moderator']:
            raise serializers.ValidationError("Bu kullanıcı adı sistem tarafından ayrılmıştır.")

        invalid_chars = set(re.findall(r'[^a-zA-ZçÇğĞıIİöÖşŞüÜâîûÂÎÛ0-9_]', value))
        if invalid_chars:
            raise serializers.ValidationError(f"Kullanıcı adında geçersiz karakterler bulundu: {' '.join(invalid_chars)}")

        if User.objects.filter(username__iexact=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Bu kullanıcı adı zaten kullanımda.")

        return value