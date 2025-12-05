from django.contrib import admin
from .models import Word, Comment, UserLike 


admin.site.register(Word)
admin.site.register(Comment)
admin.site.register(UserLike)