from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Word, Comment, Category, Notification
import unicodedata

# --- YARDIMCI FONKSİYONLAR (HELPER FUNCTIONS) ---
#
# Karakter beyaz listesi tutmuyoruz: SQL enjeksiyonunu ORM'in parametreli
# sorguları, XSS'i ise şablon autoescape'i ile frontend'deki escapeHTML() /
# textContent engelliyor. Bu yüzden < > & gibi karakterler serbesttir.
# Yalnızca görüntülenemeyen karakterler (kontrol, bidi, atanmamış) elenir.

# Klavyelerin ürettiği tipografik karakterler -> ASCII karşılığı.
_FOLD = str.maketrans({
    '‘': "'", '’': "'", '′': "'", '´': "'",
    '“': '"', '”': '"', '„': '"', '″': '"',
    '–': '-', '—': '-', '−': '-', '…': '...',
})
_INVISIBLE = ('Cc', 'Cf', 'Cs', 'Co', 'Cn')
_WORD_PUNCTUATION = " -'().,"
# q, w, x Türk alfabesinde yok ama kullanıcı adlarında yaygın ('qzan').
_USERNAME_CHARS = set('abcçdefgğhıijklmnoöprsştuüvyz' + 'qwx' + '0123456789_.')


def turkish_lower(text):
    """Türkçeye göre küçültür. Python'un .lower() metodu yanlıştır:
    'I' -> 'i' (olması gereken 'ı'), 'İ' -> 'i' + U+0307 (birleşen nokta)."""
    return text.replace('I', 'ı').replace('İ', 'i').lower() if text else ''


def clean_text(value, label, max_length):
    """Boşluk toparlar, tipografik karakterleri sadeleştirir, görünmezleri eler."""
    value = ' '.join(unicodedata.normalize('NFKC', value or '').translate(_FOLD).split())
    if not value:
        raise serializers.ValidationError(f"{label} boş olamaz.")
    if len(value) > max_length:
        raise serializers.ValidationError(f"{label} {max_length} karakteri geçemez.")
    bad = {c for c in value if unicodedata.category(c) in _INVISIBLE}
    if bad:
        names = ' '.join(sorted(unicodedata.name(c, f'U+{ord(c):04X}') for c in bad))
        raise serializers.ValidationError(f"{label} görüntülenemeyen karakter içeriyor: {names}")
    return value


def clean_word(value, label, max_length, latin_only=True):
    """Tek sözcük alanları: noktalama/simgeleri eler. `latin_only` görsel olarak
    aynı görünen harflerle (Kiril 'о' vs Latin 'o') taklidi engeller."""
    value = clean_text(value, label, max_length)
    bad = {c for c in value if not c.isalnum() and c not in _WORD_PUNCTUATION}
    if latin_only:
        bad |= {c for c in value
                if c.isalpha() and not unicodedata.name(c, '').startswith('LATIN')}
    if bad:
        raise serializers.ValidationError(f"{label} şu karakterleri içeremez: {' '.join(sorted(bad))}")
    return value


def clean_username(value):
    """Her zaman Türkçe küçük harfe çevirir; harf, rakam, alt çizgi, nokta."""
    value = turkish_lower(clean_text(value, "Kullanıcı adı", 30))
    bad = {c for c in value if c not in _USERNAME_CHARS}
    if bad:
        raise serializers.ValidationError(
            "Kullanıcı adı yalnızca harf, rakam, alt çizgi ve nokta içerebilir. "
            f"Geçersiz: {' '.join(sorted(bad))}")
    return value


def validate_example_text(value):
    """Ortak örnek cümle doğrulama mantığı"""
    return clean_text(value, "Örnek cümle", 200)


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

    def validate_word(self, value):
        return turkish_lower(clean_word(value, "Sözcük", 50))

    def validate_definition(self, value):
        return turkish_lower(clean_text(value, "Tanım", 300))

    def validate_example(self, value):
        return validate_example_text(value)
        
    def validate_etymology(self, value):
        return clean_text(value, "Köken bilgisi", 200)

    def validate_nickname(self, value):
        if not value or not value.strip():
            return "Anonim"
        value = clean_word(value, "Takma ad", 50)

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
        return clean_text(value, "Yorum", 200)
    

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
