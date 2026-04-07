from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse
from django.template import Template, RequestContext
from django.contrib.admin import helpers
from django.utils import timezone
from .models import TranslationChallenge, ChallengeComment, ChallengeCommentVote
from core.models import Notification, REJECTION_REASONS


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


@admin.action(description='Reject selected challenges (with reason)')
def reject_challenges(modeladmin, request, queryset):
    if 'apply' in request.POST:
        reason = request.POST.get('rejection_reason', '').strip()
        custom = request.POST.get('custom_reason', '').strip()
        final_reason = custom if reason == '__custom__' else reason

        if not final_reason:
            modeladmin.message_user(request, "Rejection reason cannot be empty.", level=messages.WARNING)
            return HttpResponseRedirect(request.get_full_path())

        notifications = []
        for challenge in queryset:
            challenge.status = 'rejected'
            challenge.rejection_reason = final_reason
            challenge.save(update_fields=['status', 'rejection_reason'])
            if challenge.user:
                notifications.append(Notification(
                    recipient=challenge.user,
                    notification_type='challenge_rejected',
                    message=f"{challenge.foreign_word}: {final_reason}",
                ))
        if notifications:
            Notification.objects.bulk_create(notifications)

        modeladmin.message_user(request, f"{queryset.count()} challenge(s) rejected.")
        return HttpResponseRedirect(request.get_full_path())

    reason_options = ''.join(
        f'<option value="{r[0]}">{r[1]}</option>' for r in REJECTION_REASONS
    )

    intermediate_template = Template("""
    {% extends "admin/base_site.html" %}
    {% block content %}
    <div style="max-width: 600px; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="margin-top:0;">Reject Challenges</h2>
        <p>You are about to reject <strong>{{ items|length }}</strong> challenge(s):</p>
        <ul style="background: #f8f8f8; padding: 10px 20px; border-radius: 5px; margin-bottom: 20px;">
            {% for item in items|slice:":5" %}
                <li>{{ item.foreign_word }} (by {{ item.display_author }})</li>
            {% endfor %}
            {% if items|length > 5 %}
                <li>... and {{ items|length|add:"-5" }} more.</li>
            {% endif %}
        </ul>
        <form action="" method="post">
            {% csrf_token %}
            <label for="rejection_reason" style="font-weight:bold; display:block; margin-bottom:5px;">Select Reason:</label>
            <select name="rejection_reason" id="rejection_reason" onchange="document.getElementById('custom_reason_box').style.display = this.value === '__custom__' ? 'block' : 'none';"
                    style="padding: 10px; width: 100%; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem;">
                """ + reason_options + """
                <option value="__custom__">Özel sebep yaz...</option>
            </select>
            <div id="custom_reason_box" style="display:none; margin-bottom:15px;">
                <textarea name="custom_reason" rows="3" maxlength="300" placeholder="Özel ret sebebi yazın..."
                          style="padding: 10px; width: 100%; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem; box-sizing: border-box;"></textarea>
            </div>
            {% for obj in items %}
                <input type="hidden" name="{{ action_checkbox_name }}" value="{{ obj.pk }}">
            {% endfor %}
            <input type="hidden" name="action" value="reject_challenges">
            <input type="hidden" name="apply" value="yes">
            <div style="display:flex; gap:10px;">
                <input type="submit" value="Reject" style="background: #e74c3c; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
                <a href="#" onclick="window.history.back(); return false;" style="padding: 10px 20px; text-decoration: none; color: #666; border: 1px solid #ccc; border-radius: 4px;">Cancel</a>
            </div>
        </form>
    </div>
    {% endblock %}
    """)

    context = RequestContext(request, {
        'items': queryset,
        'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
    })
    return HttpResponse(intermediate_template.render(context))


class TranslationChallengeAdmin(admin.ModelAdmin):
    actions = [approve_challenges, pending_challenges, reject_challenges, start_timer, reset_timer]
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
    search_fields = ('suggested_word', 'etymology', 'example_sentence', 'author')
    list_filter = ('timestamp',)

class ChallengeCommentVoteAdmin(admin.ModelAdmin):
    list_display = ('comment', 'user', 'value', 'timestamp')
    list_filter = ('value', 'timestamp')

admin.site.register(TranslationChallenge, TranslationChallengeAdmin)
admin.site.register(ChallengeComment, ChallengeCommentAdmin)
admin.site.register(ChallengeCommentVote, ChallengeCommentVoteAdmin)
