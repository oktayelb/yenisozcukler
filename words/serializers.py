from rest_framework import serializers
from django.contrib.auth.models import User

from common.text import (
    turkish_lower, clean_text, clean_word, validate_example_text,
)
from .models import Word, Category, Comment


# --- OKUMA (READ) SERIALIZERS ---

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description']

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

class CommentCreateSerializer(serializers.ModelSerializer):
    word_id = serializers.IntegerField()

    class Meta:
        model = Comment
        fields = ['word_id', 'comment']

    def validate_comment(self, value):
        return clean_text(value, "Yorum", 200)
    
