from django.contrib import admin

from .models import Comment, CommentVote


class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'word', 'score', 'timestamp')
    search_fields = ('comment', 'author')
    list_filter = ('timestamp',)

class CommentVoteAdmin(admin.ModelAdmin):
    list_display = ('comment', 'user', 'value', 'timestamp')
    list_filter = ('value', 'timestamp')
    search_fields = ('comment__comment', 'user__username')

# --- Register Models ---
admin.site.register(Comment, CommentAdmin)
admin.site.register(CommentVote, CommentVoteAdmin)
