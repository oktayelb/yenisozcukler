from flask import Flask, render_template, request, jsonify
import time 
import html
import re
# Düzeltme 1: utcnow() yerine UTC kullanıyoruz
from datetime import datetime, UTC 
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy.exc import SQLAlchemyError 
# İlişki tanımlamak için ihtiyacımız var
from sqlalchemy.orm import relationship, backref 

app = Flask(__name__)

# --- VERİTABANI AYARLARI ---
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
    # DÜZELTME 2: 'likes' sütunu kaldırıldı. Artık dinamik olarak sayılacak.
    # likes = db.Column(db.Integer, default=0) 
    
    # Yeni İlişki Tanımı: UserLike tablosundaki ilgili kayıtları saymak için 'likes_count' özelliği eklenir.
    # cascade="all, delete-orphan" ilişkili beğeniler silinirken kelimeyi de korur.
    liked_by = relationship("UserLike", backref="word_rel", cascade="all, delete-orphan", lazy="dynamic")
    
    # Status: 'pending' (beklemede) veya 'approved' (onaylanmış)
    status = db.Column(db.String(10), default='pending') 
    # Düzeltme 1: utcnow() yerine UTC kullanıyoruz
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def to_dict(self):
        """Frontend'e gönderilmek üzere sözcüğü sözlük formatına dönüştürür."""
        # DÜZELTME 3: likes, liked_by ilişkisinin sayısıyla (count) dinamik olarak hesaplanır.
        return {
            'id': self.id,
            'word': self.word,
            'def': self.definition,
            'author': self.author,
            'likes': self.liked_by.count(), # Dinamik sayım!
            'timestamp': self.timestamp.isoformat()
        }

# YENİ MODEL: Kullanıcı beğenilerini kalıcı olarak saklamak için
class UserLike(db.Model):
    __tablename__ = 'user_like'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False) 
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    # Düzeltme 1: utcnow() yerine UTC kullanıyoruz
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    
    __table_args__ = (db.UniqueConstraint('ip_address', 'word_id', name='_user_word_uc'),)


# Hız sınırlama için kullanılır
user_last_post_time = {}

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
    approved_words_query = Word.query.filter_by(status='approved').order_by(Word.timestamp.desc())

    client_count = request.args.get('count', type=int)
    total_count = approved_words_query.count()

    client_ip = get_client_ip()
    
    # Beğenilen ID'leri veritabanından çek
    liked_ids_query = UserLike.query.filter_by(ip_address=client_ip).all()
    liked_ids = {like.word_id for like in liked_ids_query}

    if client_count is not None and client_count == total_count:
        return jsonify({'status': 'updated', 'words': [], 'total_count': total_count})
    
    elif client_count is None or client_count < total_count:
        
        words_list = []
        
        if client_count is not None and client_count > 0:
            new_word_count = total_count - client_count
            new_words_query = approved_words_query.limit(new_word_count)
            words_list = [word.to_dict() for word in new_words_query.all()]
            status = 'updated'
        
        else:
            words_list = [word.to_dict() for word in approved_words_query.limit(50).all()]
            status = 'full'
        
        # Her kelimenin beğenilip beğenilmediği bilgisini ekle
        for word_data in words_list:
            word_data['is_liked'] = word_data['id'] in liked_ids

        return jsonify({'status': status, 'words': words_list, 'total_count': total_count})
    
    else:
        words_list = [word.to_dict() for word in approved_words_query.limit(50).all()]
        for word_data in words_list:
            word_data['is_liked'] = word_data['id'] in liked_ids
            
        return jsonify({'status': 'full', 'words': words_list, 'total_count': total_count})


# --- YENİ ENDPOINT: Oylama Sistemi için ---
@app.route('/api/like/<int:word_id>', methods=['POST'])
def toggle_like(word_id):
    client_ip = get_client_ip()
    
    # DÜZELTME 4: Word.query.get() yerine db.session.get() kullanıldı.
    word_to_update = db.session.get(Word, word_id)
    if not word_to_update or word_to_update.status != 'approved':
        return jsonify({'success': False, 'error': 'Geçersiz sözcük.'}), 404
        
    try:
        existing_like = UserLike.query.filter_by(ip_address=client_ip, word_id=word_id).first()
        
        if existing_like:
            # Beğeni Geri Çekme (Unlike)
            # DÜZELTME 5: Word.likes artık dinamik olduğu için elle azaltmaya gerek yok, 
            # sadece UserLike kaydını silmek yeterli.
            db.session.delete(existing_like) 
            action = 'unliked'
        else:
            # Beğenme (Like)
            # DÜZELTME 5: Word.likes artık dinamik olduğu için elle artırmaya gerek yok, 
            # sadece UserLike kaydını eklemek yeterli.
            new_like = UserLike(ip_address=client_ip, word_id=word_id) # timestamp zaten otomatik
            db.session.add(new_like) 
            action = 'liked'
            
        db.session.commit()
        
        # DÜZELTME 6: Beğeni sayısı Commit sonrası dinamic olarak yeniden hesaplanır.
        return jsonify({
            'success': True, 
            'action': action,
            'new_likes': word_to_update.liked_by.count(), # Dinamik sayıyı döndür
            'word_id': word_id
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Veritabanı beğeni hatası: {e}")
        return jsonify({'success': False, 'error': 'Sunucu hatası.'}), 500


# --- YENİLENEN ENDPOINT: /api/add ---
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
            # Düzeltme 1: timestamp otomatik olarak UTC'ye ayarlanır
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