from django.contrib import admin
from django.utils import timezone
from .models import TranslationChallenge, ChallengeComment, ChallengeCommentVote


@admin.action(description='Mark selected challenges as Approved')
def approve_challenges(modeladmin, request, queryset):
    updated_count = queryset.update(status='approved')
    modeladmin.message_user(request, f"{updated_count} challenges marked as Approved.")

@admin.action(description='Mark selected challenges as Pending')
def pending_challenges(modeladmin, request, queryset):
    updated_count = queryset.update(status='pending')
    modeladmin.message_user(request, f"{updated_count} challenges marked as Pending.")

@admin.action(description='Start 7-day timer (set timer on)')
def start_timer(modeladmin, request, queryset):
    updated_count = queryset.filter(timer_on=False).update(timer_on=True, timer_started_at=timezone.now())
    modeladmin.message_user(request, f"Timer started for {updated_count} challenges.")

@admin.action(description='Reset timer (turn off)')
def reset_timer(modeladmin, request, queryset):
    updated_count = queryset.update(timer_on=False, timer_started_at=None)
    modeladmin.message_user(request, f"Timer reset for {updated_count} challenges.")


class TranslationChallengeAdmin(admin.ModelAdmin):
    actions = [approve_challenges, pending_challenges, start_timer, reset_timer]
    list_display = ('foreign_word', 'meaning', 'status', 'author', 'user', 'timer_on', 'timer_started_at', 'timestamp')
    list_filter = ('status', 'timer_on', 'timestamp')
    search_fields = ('foreign_word', 'meaning', 'author')
    list_editable = ('timer_on',)

    def save_model(self, request, obj, form, change):
        if change and 'timer_on' in form.changed_data:
            if obj.timer_on and not obj.timer_started_at:
                obj.timer_started_at = timezone.now()
            elif not obj.timer_on:
                obj.timer_started_at = None
        super().save_model(request, obj, form, change)


class ChallengeCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'challenge', 'suggested_word', 'score', 'timestamp')
    search_fields = ('suggested_word', 'etymology', 'example_sentence', 'explanation', 'author')
    list_filter = ('timestamp',)

class ChallengeCommentVoteAdmin(admin.ModelAdmin):
    list_display = ('comment', 'user', 'value', 'timestamp')
    list_filter = ('value', 'timestamp')

admin.site.register(TranslationChallenge, TranslationChallengeAdmin)
admin.site.register(ChallengeComment, ChallengeCommentAdmin)
admin.site.register(ChallengeCommentVote, ChallengeCommentVoteAdmin)
