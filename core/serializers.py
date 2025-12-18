from rest_framework import serializers
from .models import Word, Comment
import re

# --- OKUMA (READ) SERIALIZERS ---

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'word', 'author', 'comment', 'timestamp']

class WordSerializer(serializers.ModelSerializer):
    likes = serializers.IntegerField(source='likes.count', read_only=True)
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Word
        fields = ['id', 'word', 'author', 'likes', 'timestamp', 'is_liked', 'is_profane', 'definition'] 
        # Not: Modelde 'definition' alanı var, ancak sen to_representation ile 'def' olarak dönüyordun.
        # Frontend'i bozmamak için aşağıda map edeceğiz veya model field ismini kullanacağız.
        # Clean code için model field ismini kullanmak daha iyidir ama frontend uyumu için 'to_representation'ı koruyoruz.

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
        if value:
            value = value.strip()
            if not re.match(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9]*$', value):
                raise serializers.ValidationError("Takma ad geçersiz karakterler içeriyor.")
        return value if value else "Anonim"

class CommentCreateSerializer(serializers.ModelSerializer):
    word_id = serializers.IntegerField()
    
    class Meta:
        model = Comment
        fields = ['word_id', 'author', 'comment']

    def validate_comment(self, value):
        value = value.strip()
        if len(value) > 200:
            raise serializers.ValidationError("Yorum 200 karakteri geçemez.")
        if not value:
            raise serializers.ValidationError("Yorum boş olamaz.")
        return value

    def validate_author(self, value):
        return value.strip() if value else "Anonim"