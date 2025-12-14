from rest_framework import serializers
from .models import Word, Comment

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'word', 'author', 'comment', 'timestamp']

class WordSerializer(serializers.ModelSerializer):

    likes = serializers.IntegerField(source='likes.count', read_only=True)
    
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Word
        
        fields = ['id', 'word', 'author', 'likes', 'timestamp', 'is_liked','is_profane']

    def get_is_liked(self, obj):

        liked_ids = self.context.get('liked_ids', set())
        return obj.id in liked_ids

    def to_representation(self, instance):

        data = super().to_representation(instance)
        data['def'] = instance.definition 
        return data