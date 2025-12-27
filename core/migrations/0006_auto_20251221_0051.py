
# core/migrations/00XX_dosya_adi.py
from django.db import migrations

def transfer_data(apps, schema_editor):
    # Modelleri geçmiş versiyonlarıyla çağırıyoruz
    Word = apps.get_model('core', 'Word')
    UserLike = apps.get_model('core', 'UserLike')  # Eski Model
    WordVote = apps.get_model('core', 'WordVote')  # Yeni Model

    # 1. ESKİ 'UserLike' VERİLERİNİ 'WordVote'A TAŞI
    # Eski sistemde sadece 'beğeni' vardı, bu yüzden value=1 veriyoruz.
    existing_likes = UserLike.objects.all()
    new_votes = []
    for like in existing_likes:
        new_votes.append(WordVote(
            ip_address=like.ip_address,
            word=like.word,
            value=1,  # 1 = Like
            timestamp=like.timestamp
        ))
    # Hepsini tek seferde kaydet (Performans için bulk_create)
    WordVote.objects.bulk_create(new_votes, ignore_conflicts=True)

    # 2. ESKİ 'likes_count' DEĞERİNİ 'score'A TAŞI
    for word in Word.objects.all():
        word.score = word.likes_count
        word.save()

class Migration(migrations.Migration):

    dependencies = [
        # BURASI ÇOK ÖNEMLİ: 
        # Bir önceki (1. Adımda oluşan) dosyanın adı burada yazmalı.
        ('core', '0005_comment_score_word_score_commentvote_wordvote'),
    ]

    operations = [
        migrations.RunPython(transfer_data),
    ]