from flask import Flask, render_template, request, jsonify
import time 
import html
import re
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy.exc import SQLAlchemyError # Veritabanı hatalarını yönetmek için

app = Flask(__name__)

# --- VERİTABANI AYARLARI ---
# SQLite dosyasının yolunu tanımla
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sozluk.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) 

PORT = 5000

# --- VERİTABANI MODELİ ---
class Word(db.Model):
    # Tablo Adı: Word
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), nullable=False)
    definition = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(20), default='Anonymous')
    likes = db.Column(db.Integer, default=0) 
    # Status: 'pending' (beklemede) veya 'approved' (onaylanmış)
    status = db.Column(db.String(10), default='pending') 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Frontend'e gönderilmek üzere sözcüğü sözlük formatına dönüştürür."""
        return {
            'id': self.id,
            'word': self.word,
            'def': self.definition,
            'author': self.author,
            'likes': self.likes,
            'timestamp': self.timestamp.isoformat()
        }

# Hız sınırlama için kullanılır
user_last_post_time = {}

# YENİ: Kullanıcıların hangi kelimeleri beğendiğini IP adresine göre takip eder.
# Yapı: { ip_adresi: { word_id: timestamp } }
user_likes = {} 

# Sadece harf, rakam, boşluk, nokta veya virgül
ALPHANUM_WITH_SPACES = re.compile(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9]*$')


def create_tables():
    """Uygulama bağlamı içinde veritabanı tablosunu oluşturur."""
    db.create_all()

def get_client_ip():
    # Güvenlik için X-Forwarded-For başlığını kullanmak daha doğru olabilir, 
    # ancak yerel çalışma ortamı için remote_addr yeterlidir.
    return request.remote_addr


@app.route('/')
def index():
    return render_template('index.html')


# --- YENİLENEN ENDPOINT: /api/words ---
@app.route('/api/words', methods=['GET'])
def get_words():
    # En yeni onaylanmış sözcükleri (maksimum 50) al
    # Sıralama: eklenme tarihine göre (en yeni en başta)
    approved_words_query = Word.query.filter_by(status='approved').order_by(Word.timestamp.desc())

    client_count = request.args.get('count', type=int)
    total_count = approved_words_query.count()

    # Kullanıcının beğeni durumunu döndürmek için IP adresini al
    client_ip = get_client_ip()
    liked_ids = user_likes.get(client_ip, {}).keys()

    # Eğer client'ın bildiği sayı total_count'a eşitse, yeni bir şey yok
    if client_count is not None and client_count == total_count:
        return jsonify({'status': 'updated', 'words': [], 'total_count': total_count})
    
    # Client'ın saydığı kelime sayısı daha az veya ilk yükleme ise
    elif client_count is None or client_count < total_count:
        
        words_list = []
        
        # Eğer client'ın bildiği sayı varsa, aradaki farkı (yeni eklenenleri) bul ve gönder
        if client_count is not None and client_count > 0:
            new_word_count = total_count - client_count
            new_words_query = approved_words_query.limit(new_word_count)
            words_list = [word.to_dict() for word in new_words_query.all()]
            status = 'updated'
        
        # Client'ta hiç kelime yoksa veya ilk yükleme ise (client_count = None), ilk 50'yi gönder
        else:
            words_list = [word.to_dict() for word in approved_words_query.limit(50).all()]
            status = 'full'
        
        # Her kelimenin beğenilip beğenilmediği bilgisini ekle
        for word_data in words_list:
            word_data['is_liked'] = word_data['id'] in liked_ids

        return jsonify({'status': status, 'words': words_list, 'total_count': total_count})
    
    # client_count > total_count ise (client'ta fazlalık var), full listeyi gönder
    else:
        words_list = [word.to_dict() for word in approved_words_query.limit(50).all()]
        for word_data in words_list:
            word_data['is_liked'] = word_data['id'] in liked_ids
            
        return jsonify({'status': 'full', 'words': words_list, 'total_count': total_count})


# --- YENİ ENDPOINT: Oylama Sistemi için ---
@app.route('/api/like/<int:word_id>', methods=['POST'])
def toggle_like(word_id):
    client_ip = get_client_ip()
    current_time = time.time()
    
    # IP'ye göre beğeni durumu takibi
    ip_likes = user_likes.setdefault(client_ip, {})
    
    # Hız sınırı: Aynı kelimeyi 1 saniye içinde tekrar beğenme/geri çekme yasağı
    last_like_time = ip_likes.get(word_id, 0)
    if current_time - last_like_time < 1:
        return jsonify({'success': False, 'error': 'Lütfen biraz bekleyin.'}), 429
    
    word_to_update = Word.query.get(word_id)
    if not word_to_update or word_to_update.status != 'approved':
        return jsonify({'success': False, 'error': 'Geçersiz sözcük.'}), 404
        
    try:
        is_liked_by_user = word_id in ip_likes
        
        if is_liked_by_user:
            # Beğeni Geri Çekme (Unlike)
            word_to_update.likes = max(0, word_to_update.likes - 1)
            del ip_likes[word_id]
            action = 'unliked'
        else:
            # Beğenme (Like)
            word_to_update.likes += 1
            ip_likes[word_id] = current_time
            action = 'liked'
            
        db.session.commit()
        
        # Frontend'e güncel beğeni sayısı ve yapılan eylemi döndür
        return jsonify({
            'success': True, 
            'action': action,
            'new_likes': word_to_update.likes,
            'word_id': word_id
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Veritabanı beğeni hatası: {e}")
        return jsonify({'success': False, 'error': 'Sunucu hatası.'}), 500


# --- YENİLENEN ENDPOINT: /api/add ---
# Bu kısım önceki haliyle korundu, sadece burayı da tamamlamış olalım.
@app.route('/api/add', methods=['POST'])
def add_word():
    ip = get_client_ip()
    current_time = time.time()
    
    if ip in user_last_post_time and (current_time - user_last_post_time.get(ip, 0) < 30):
        return jsonify({'success': False, 'error': 'Çok hızlı gönderiyorsunuz. Lütfen 30 saniye bekleyin.'}), 429
    
    data = request.get_json()
    word = data.get('word', '').strip()
    definition = data.get('definition', '').strip()
    nickname = data.get('nickname', '').strip()

    # Doğrulama (Validation)
    if not word or not ALPHANUM_WITH_SPACES.match(word):
        return jsonify({'success': False, 'error': 'Sözcük alanı geçersiz.'}), 400

    if nickname and not ALPHANUM_WITH_SPACES.match(nickname):
        return jsonify({'success': False, 'error': 'Takma ad geçersiz.'}), 400

    if not definition or not ALPHANUM_WITH_SPACES.match(definition):
        return jsonify({'success': False, 'error': 'Tanım geçersiz.'}), 400

    if not nickname:
        nickname = 'Anonymous'

    if len(word) > 50 or len(definition) > 300 or len(nickname) > 20:
        return jsonify({'success': False, 'error': 'Metin çok uzun.'}), 400

    clean_word = html.escape(word)
    clean_def = html.escape(definition)
    clean_nick = html.escape(nickname)

    try:
        new_word_submission = Word(
            word=clean_word,
            definition=clean_def,
            author=clean_nick,
            status='pending', 
            timestamp=datetime.utcnow()
        )
        
        db.session.add(new_word_submission)
        db.session.commit() 
        
    except Exception as e:
        db.session.rollback()
        print(f"Veritabanı hatası: {e}")
        return jsonify({'success': False, 'error': 'Sözcük kaydedilirken sunucu hatası oluştu.'}), 500

    user_last_post_time[ip] = time.time()

    return jsonify({'success': True})


if __name__ == '__main__':
    with app.app_context():
        create_tables() 
    app.run(debug=True, port=PORT)