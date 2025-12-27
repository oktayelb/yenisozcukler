from django.contrib import admin
from .models import Word, Comment, WordVote, CommentVote

# --- Define Actions ---

@admin.action(description='Mark selected words as Approved')
def make_approved(modeladmin, request, queryset):
    updated_count = queryset.update(status='approved')
    modeladmin.message_user(request, f"{updated_count} words marked as Approved.")

@admin.action(description='Mark selected words as Pending')
def make_pending(modeladmin, request, queryset):
    updated_count = queryset.update(status='pending')
    modeladmin.message_user(request, f"{updated_count} words marked as Pending.")

# --- Define Admin Classes ---

class WordAdmin(admin.ModelAdmin):
    actions = [make_approved, make_pending]
    
    # 'score' eklendi, likes_count kaldırıldı.
    list_display = ('word', 'status', 'score', 'author', 'timestamp', 'is_profane')
    
    # Filtreleme seçenekleri
    list_filter = ('status', 'is_profane', 'timestamp')
    
    # Yönetim panelinde arama yapabilmek için
    search_fields = ('word', 'definition', 'author')

class CommentAdmin(admin.ModelAdmin):
    # Yorumları takip etmek için özel görünüm
    list_display = ('author', 'word', 'score', 'timestamp')
    search_fields = ('comment', 'author')
    list_filter = ('timestamp',)

class WordVoteAdmin(admin.ModelAdmin):
    # Hangi IP hangi kelimeye ne oy vermiş (1 veya -1)
    list_display = ('word', 'ip_address', 'value', 'timestamp')
    list_filter = ('value', 'timestamp')
    search_fields = ('ip_address', 'word__word')

class CommentVoteAdmin(admin.ModelAdmin):
    # Hangi IP hangi yoruma ne oy vermiş
    list_display = ('comment', 'ip_address', 'value', 'timestamp')
    list_filter = ('value', 'timestamp')
    search_fields = ('ip_address', 'comment__comment')

# --- Register Models ---

admin.site.register(Word, WordAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(WordVote, WordVoteAdmin)
admin.site.register(CommentVote, CommentVoteAdmin)