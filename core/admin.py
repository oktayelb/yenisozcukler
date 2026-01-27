from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse
from django.template import Template, RequestContext
from django.contrib.admin import helpers
# Added Category to imports
from .models import Word, Comment, WordVote, CommentVote, Category
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

# --- Define Actions ---

@admin.action(description='Mark selected words as Approved')
def make_approved(modeladmin, request, queryset):
    updated_count = queryset.update(status='approved')
    modeladmin.message_user(request, f"{updated_count} words marked as Approved.")

@admin.action(description='Mark selected words as Pending')
def make_pending(modeladmin, request, queryset):
    updated_count = queryset.update(status='pending')
    modeladmin.message_user(request, f"{updated_count} words marked as Pending.")

@admin.action(description='Change Author (Text Input)')
def change_author(modeladmin, request, queryset):
    # 1. If the user clicked "Update Author" in the intermediate form
    if 'apply' in request.POST:
        new_author_name = request.POST.get('new_author_name', '').strip()
        
        if new_author_name:
            # Smart Linking Logic:
            # Check if a real user exists with this username (case-insensitive)
            # If yes, link them. If no, set user=None (pure string author).
            user_match = User.objects.filter(username__iexact=new_author_name).first()
            
            # Update the selected words
            updated_count = queryset.update(
                author=new_author_name, 
                user=user_match # This will be the User object OR None
            )
            
            msg = f"Successfully changed author to '{new_author_name}' for {updated_count} words."
            if user_match:
                msg += f" (Linked to registered user: {user_match.username})"
            else:
                msg += " (No registered user found; set as string only)."
                
            modeladmin.message_user(request, msg)
            return HttpResponseRedirect(request.get_full_path())
        else:
            modeladmin.message_user(request, "Author name cannot be empty.", level=messages.WARNING)
            return HttpResponseRedirect(request.get_full_path())

    # 2. If this is the first click, show the selection form (Template)
    intermediate_template = Template("""
    {% extends "admin/base_site.html" %}
    {% block content %}
    <div style="max-width: 600px; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="margin-top:0;">Change Author (String Update)</h2>
        <p>You are about to change the author text for the following <strong>{{ words|length }}</strong> word(s):</p>
        
        <ul style="background: #f8f8f8; padding: 10px 20px; border-radius: 5px; margin-bottom: 20px;">
            {% for word in words|slice:":5" %}
                <li>{{ word.word }} (Current: <strong>{{ word.author }}</strong>)</li>
            {% endfor %}
            {% if words|length > 5 %}
                <li>... and {{ words|length|add:"-5" }} more.</li>
            {% endif %}
        </ul>

        <form action="" method="post">
            {% csrf_token %}
            
            <label for="new_author_name" style="font-weight:bold; display:block; margin-bottom:5px;">Enter New Author Name:</label>
            
            <input type="text" name="new_author_name" id="new_author_name" placeholder="Type author name here..." required
                   style="padding: 10px; width: 100%; margin-bottom: 20px; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem;">
            
            <p style="font-size: 0.9rem; color: #666; margin-top: -15px; margin-bottom: 20px;">
                * If this matches a registered username, the account will be linked automatically.
            </p>

            {% for obj in words %}
                <input type="hidden" name="{{ action_checkbox_name }}" value="{{ obj.pk }}">
            {% endfor %}
            <input type="hidden" name="action" value="change_author">
            <input type="hidden" name="apply" value="yes">
            
            <div style="display:flex; gap:10px;">
                <input type="submit" value="Update Author" style="background: var(--primary); color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
                <a href="#" onclick="window.history.back(); return false;" style="padding: 10px 20px; text-decoration: none; color: #666; border: 1px solid #ccc; border-radius: 4px;">Cancel</a>
            </div>
        </form>
    </div>
    {% endblock %}
    """)

    context = RequestContext(request, {
        'words': queryset,
        'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        'site_header': modeladmin.admin_site.site_header,
        'site_title': modeladmin.admin_site.site_title,
    })

    return HttpResponse(intermediate_template.render(context))

# --- Define Admin Classes ---

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'order')
    list_editable = ('is_active', 'order') # Edit these directly in the list
    prepopulated_fields = {'slug': ('name',)} # Auto-fill slug from name
    ordering = ('order', 'name')

class WordAdmin(admin.ModelAdmin):
    actions = [make_approved, make_pending, change_author]
    
    list_display = ('word', 'status', 'score', 'author', 'user', 'timestamp', 'is_profane')
    # Added 'categories' to list_filter so you can filter words by category
    list_filter = ('status', 'is_profane', 'categories', 'timestamp')
    search_fields = ('word', 'definition', 'author')
    # Use a better widget for selecting multiple categories
    filter_horizontal = ('categories',)

class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'word', 'score', 'timestamp')
    search_fields = ('comment', 'author')
    list_filter = ('timestamp',)

class WordVoteAdmin(admin.ModelAdmin):
    list_display = ('word', 'ip_address', 'value', 'timestamp')
    list_filter = ('value', 'timestamp')
    search_fields = ('ip_address', 'word__word')

class CommentVoteAdmin(admin.ModelAdmin):
    list_display = ('comment', 'ip_address', 'value', 'timestamp')
    list_filter = ('value', 'timestamp')
    search_fields = ('ip_address', 'comment__comment')

class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

# --- Register Models ---
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

admin.site.register(Category, CategoryAdmin) # Registered Category
admin.site.register(Word, WordAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(WordVote, WordVoteAdmin)
admin.site.register(CommentVote, CommentVoteAdmin)