"""Türkçe metin normalleştirme ve doğrulama yardımcıları.

Saf metin işlemleri; hiçbir model içe aktarmaz. `core` ve `challenge`
serializer'ları buradaki `clean_*` fonksiyonlarını paylaşır.
"""

import re
import unicodedata

from rest_framework import serializers


# --- YARDIMCI FONKSİYONLAR (HELPER FUNCTIONS) ---
#
# Karakter beyaz listesi tutmuyoruz: SQL enjeksiyonunu ORM'in parametreli
# sorguları, XSS'i ise şablon autoescape'i ile frontend'deki escapeHTML() /
# textContent engelliyor. Bu yüzden < > & gibi karakterler serbesttir.
# Yalnızca görüntülenemeyen karakterler (kontrol, bidi, atanmamış) elenir.

# Klavyelerin ürettiği tipografik karakterler -> ASCII karşılığı.
_FOLD = str.maketrans({
    '‘': "'", '’': "'", '′': "'", '´': "'",
    '“': '"', '”': '"', '„': '"', '″': '"',
    '–': '-', '—': '-', '−': '-', '…': '...',
})
_INVISIBLE = ('Cc', 'Cf', 'Cs', 'Co', 'Cn')
_WORD_PUNCTUATION = " -'().,"
# q, w, x Türk alfabesinde yok ama kullanıcı adlarında yaygın ('qzan').
_USERNAME_CHARS = set('abcçdefgğhıijklmnoöprsştuüvyz' + 'qwx' + '0123456789_.')


def turkish_lower(text):
    """Türkçeye göre küçültür. Python'un .lower() metodu yanlıştır:
    'I' -> 'i' (olması gereken 'ı'), 'İ' -> 'i' + U+0307 (birleşen nokta)."""
    return text.replace('I', 'ı').replace('İ', 'i').lower() if text else ''


def clean_text(value, label, max_length):
    """Boşluk toparlar, tipografik karakterleri sadeleştirir, görünmezleri eler."""
    value = ' '.join(unicodedata.normalize('NFKC', value or '').translate(_FOLD).split())
    if not value:
        raise serializers.ValidationError(f"{label} boş olamaz.")
    if len(value) > max_length:
        raise serializers.ValidationError(f"{label} {max_length} karakteri geçemez.")
    bad = {c for c in value if unicodedata.category(c) in _INVISIBLE}
    if bad:
        names = ' '.join(sorted(unicodedata.name(c, f'U+{ord(c):04X}') for c in bad))
        raise serializers.ValidationError(f"{label} görüntülenemeyen karakter içeriyor: {names}")
    return value


def clean_word(value, label, max_length, latin_only=True):
    """Tek sözcük alanları: noktalama/simgeleri eler. `latin_only` görsel olarak
    aynı görünen harflerle (Kiril 'о' vs Latin 'o') taklidi engeller."""
    value = clean_text(value, label, max_length)
    bad = {c for c in value if not c.isalnum() and c not in _WORD_PUNCTUATION}
    if latin_only:
        bad |= {c for c in value
                if c.isalpha() and not unicodedata.name(c, '').startswith('LATIN')}
    if bad:
        raise serializers.ValidationError(f"{label} şu karakterleri içeremez: {' '.join(sorted(bad))}")
    return value


def clean_username(value):
    """Her zaman Türkçe küçük harfe çevirir; harf, rakam, alt çizgi, nokta."""
    value = turkish_lower(clean_text(value, "Kullanıcı adı", 30))
    bad = {c for c in value if c not in _USERNAME_CHARS}
    if bad:
        raise serializers.ValidationError(
            "Kullanıcı adı yalnızca harf, rakam, alt çizgi ve nokta içerebilir. "
            f"Geçersiz: {' '.join(sorted(bad))}")
    return value


def validate_example_text(value):
    """Ortak örnek cümle doğrulama mantığı"""
    return clean_text(value, "Örnek cümle", 200)


TURKISH_CHAR_MAP = {
    'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
    'â': 'a', 'î': 'i', 'û': 'u',
}


def turkish_to_ascii(text):
    text = text.lower()
    for tr, en in TURKISH_CHAR_MAP.items():
        text = text.replace(tr, en)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')
