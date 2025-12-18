from rest_framework import serializers
from .models import Word, Comment
import re

# --- OKUMA (READ) SERIALIZERS ---

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'word', 'author', 'comment', 'timestamp']

class WordSerializer(serializers.ModelSerializer):
    # GÜNCELLEME: source='annotated_likes' olarak değiştirildi.
    # Artık veritabanını sorgulamıyor, View'dan gelen hazır veriyi okuyor.
    likes = serializers.IntegerField(source='annotated_likes', read_only=True)
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Word
        fields = ['id', 'word', 'author', 'likes', 'timestamp', 'is_liked', 'is_profane', 'definition'] 

    def get_is_liked(self, obj):
        liked_ids = self.context.get('liked_ids', set())
        return obj.id in liked_ids

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['def'] = instance.definition 
        return data

# --- YAZMA (WRITE/CREATE) SERIALIZERS ---

class WordCreateSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(source='author', required=False, allow_blank=True, max_length=50)
    
    class Meta:
        model = Word
        fields = ['word', 'definition', 'nickname', 'is_profane']

    def validate_word(self, value):
        value = value.strip()
        if not re.match(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9]+$', value):
            raise serializers.ValidationError("Sözcük sadece harf, rakam ve temel noktalama işaretleri içerebilir.")
        return value

    def validate_definition(self, value):
        value = value.strip()
        if not re.match(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9]+$', value):
            raise serializers.ValidationError("Tanım geçersiz karakterler içeriyor.")
        return value

    def validate_nickname(self, value):
        if not value or not value.strip():
            return "Anonim"
        if value:
            value = value.strip()
            if not re.match(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9]*$', value):
                raise serializers.ValidationError("Takma ad geçersiz karakterler içeriyor.")
        return value 

class CommentCreateSerializer(serializers.ModelSerializer):
    word_id = serializers.IntegerField()
    
    class Meta:
        model = Comment
        fields = ['word_id', 'author', 'comment']
        # EKLEMEN GEREKEN KISIM:
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
        # extra_kwargs sayesinde artık buraya boş string ("") düşebilir.
        # Senin mantığın burada devreye girip onu "Anonim" yapar.
        return value.strip() if value else "Anonim"