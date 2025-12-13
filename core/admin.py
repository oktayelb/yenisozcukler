from django.contrib import admin
from .models import Word, Comment, UserLike

# --- Define Actions ---

@admin.action(description='Mark selected words as Approved')
def make_approved(modeladmin, request, queryset):
    updated_count = queryset.update(status='approved')
    modeladmin.message_user(request, f"{updated_count} words marked as Approved.")

@admin.action(description='Mark selected words as Pending')
def make_pending(modeladmin, request, queryset):
    updated_count = queryset.update(status='pending')
    modeladmin.message_user(request, f"{updated_count} words marked as Pending.")

# --- Define Admin Class ---

class WordAdmin(admin.ModelAdmin):
    # The actions we defined above
    actions = [make_approved, make_pending]
    
    # FIXED: Changed 'content' to 'word' to match your model
    list_display = ('word', 'status', 'author', 'timestamp')
    
    # Optional: Adds a sidebar filter for Status (Pending/Approved)
    list_filter = ('status',)

# --- Register Models ---

admin.site.register(Word, WordAdmin)
admin.site.register(Comment)
admin.site.register(UserLike)