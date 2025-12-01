from flask import Flask, render_template, request, jsonify
import time 
import html
import re
from datetime import datetime, UTC 
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy.exc import SQLAlchemyError 
from sqlalchemy.orm import relationship, backref 

app = Flask(__name__)

# --- VERİTABANI AYARLARI ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sozluk.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) 

PORT = 5000

# --- VERİTABANI MODELİ ---
class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), nullable=False)
    definition = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(20), default='Anonymous')
    
    liked_by = db.relationship("UserLike", backref="word_rel", cascade="all, delete-orphan", lazy="dynamic")
    
    status = db.Column(db.String(10), default='pending') 
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def to_dict(self):
        """Frontend'e gönderilmek üzere sözcüğü sözlük formatına dönüştürür."""
        return {
            'id': self.id,
            'word': self.word,
            'def': self.definition,
            'author': self.author,
            'likes': self.liked_by.count(), 
            'timestamp': self.timestamp.isoformat()
        }

class UserLike(db.Model):
    __tablename__ = 'user_like'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False) 
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    
    __table_args__ = (db.UniqueConstraint('ip_address', 'word_id', name='_user_word_uc'),)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False) 
    
    author = db.Column(db.String(50), default='Anonim') 
    
    comment = db.Column(db.String(200), nullable=False) 
    
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def to_dict(self):
        """Frontend'e gönderilmek üzere yorumu sözlük formatına dönüştürür."""
        return {
            'id': self.id,
            'word_id': self.word_id,
            'author': self.author,
            'comment': self.comment,
            'timestamp': self.timestamp.isoformat() 
        }

user_last_post_time = {}

# YENİ EKLENEN: Yorumlar için hız limitini tutar
user_last_comment_time = {}

ALPHANUM_WITH_SPACES = re.compile(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9]*$')


def create_tables():
    """Uygulama bağlamı içinde veritabanı tablosunu oluşturur."""
    db.create_all()

def get_client_ip():
    return request.remote_addr


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/words', methods=['GET'])
def get_words():
    approved_words_query = Word.query.filter_by(status='approved').order_by(Word.timestamp.desc())

    total_count = approved_words_query.count()

    client_ip = get_client_ip()
    
    liked_ids_query = UserLike.query.filter_by(ip_address=client_ip).all()
    liked_ids = {like.word_id for like in liked_ids_query}

    words_list = [word.to_dict() for word in approved_words_query.limit(50).all()]
    
    for word_data in words_list:
        word_data['is_liked'] = word_data['id'] in liked_ids

    return jsonify({'status': 'full', 'words': words_list, 'total_count': total_count})


@app.route('/api/like/<int:word_id>', methods=['POST'])
def toggle_like(word_id):
    client_ip = get_client_ip()
    
    word_to_update = db.session.get(Word, word_id)
    if not word_to_update or word_to_update.status != 'approved':
        return jsonify({'success': False, 'error': 'Geçersiz sözcük.'}), 404
        
    try:
        existing_like = UserLike.query.filter_by(ip_address=client_ip, word_id=word_id).first()
        
        if existing_like:
            db.session.delete(existing_like) 
            action = 'unliked'
            log_message = f"DISLIKED: Word ID {word_id} by {client_ip}"
        else:
            new_like = UserLike(ip_address=client_ip, word_id=word_id)
            db.session.add(new_like) 
            action = 'liked'
            log_message = f"LIKED: Word ID {word_id} by {client_ip}"
            
        db.session.commit()
        
        print(log_message)
        
        return jsonify({
            'success': True, 
            'action': action,
            'new_likes': word_to_update.liked_by.count(),
            'word_id': word_id
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Veritabanı beğeni hatası: {e}")
        return jsonify({'success': False, 'error': 'Sunucu hatası.'}), 500


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
        )
        
        db.session.add(new_word_submission)
        db.session.commit() 
        
    except Exception as e:
        db.session.rollback()
        print(f"Veritabanı hatası: {e}")
        return jsonify({'success': False, 'error': 'Sözcük kaydedilirken sunucu hatası oluştu.'}), 500

    user_last_post_time[ip] = time.time()

    return jsonify({'success': True})


# YENİ ENDPOINT: Yorum ekleme (Hız limiti eklendi)
@app.route('/api/comment/add', methods=['POST'])
def add_comment():
    ip = get_client_ip()
    current_time = time.time()

    # HIZ LİMİTİ KONTROLÜ
    if ip in user_last_comment_time and (current_time - user_last_comment_time.get(ip, 0) < 30):
        remaining_time = 30 - int(current_time - user_last_comment_time.get(ip, 0))
        return jsonify({'success': False, 'error': f'Çok hızlı yorum gönderiyorsunuz. Lütfen {remaining_time} saniye bekleyin.'}), 429
    
    data = request.get_json()
    word_id = data.get('word_id', None)
    author = data.get('author', 'Anonim').strip()
    comment_text = data.get('comment', '').strip()

    if not word_id or not comment_text:
        return jsonify({'success': False, 'error': 'Eksik parametreler.'}), 400

    if len(comment_text) > 200:
        return jsonify({'success': False, 'error': 'Yorum 200 karakterden uzun olamaz.'}), 400

    # Kelimenin varlığını kontrol et
    word_exists = db.session.get(Word, word_id)
    if not word_exists:
         return jsonify({'success': False, 'error': 'Geçersiz sözcük ID.'}), 404

    # HTML kaçış (sanitasyon)
    clean_author = html.escape(author)[:50]
    clean_comment = html.escape(comment_text)
    
    try:
        new_comment = Comment(
            word_id=word_id,
            author=clean_author,
            comment=clean_comment
        )
        db.session.add(new_comment)
        db.session.commit()
        
        print(f"COMMENT ADDED: Word ID {word_id} by {clean_author}")
        
        # BAŞARILI KAYITTAN SONRA ZAMAN DAMGASINI GÜNCELLE
        user_last_comment_time[ip] = current_time 

        return jsonify({
            'success': True,
            'comment': new_comment.to_dict() # Yeni eklenen yorumu geri gönder
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Yorum ekleme hatası: {e}")
        return jsonify({'success': False, 'error': 'Yorum kaydedilirken sunucu hatası oluştu.'}), 500

# Yorumları çekme endpoint'i (sıralama ASC)
@app.route('/api/comments/<int:word_id>', methods=['GET'])
def get_comments(word_id):
    comments = Comment.query.filter_by(word_id=word_id).order_by(Comment.timestamp.asc()).all()
    
    comments_list = [comment.to_dict() for comment in comments]
    
    return jsonify({'success': True, 'comments': comments_list})


if __name__ == '__main__':
    with app.app_context():
        create_tables() 
    app.run(debug=True, port=PORT)