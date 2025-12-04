from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, abort 
import time 
import html
import re
from functools import wraps
from werkzeug.security import check_password_hash


from instance.models import Word, UserLike, Comment, db 
from config_secrets import SECRET_KEY, ADMIN_HASH
from secrets1 import get_daily_admin_path

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sozluk.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = SECRET_KEY


# 2. GİRİŞ ŞİFRESİ:
ADMIN_PASSWORD_HASH = ADMIN_HASH 


db.init_app(app) 

PORT = 5000

# --- HELPERS (Aynı kalır) ---
user_last_post_time = {}
user_last_comment_time = {}
ALPHANUM_WITH_SPACES = re.compile(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9]*$')

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

# --- ADMIN DECORATOR (Aynı kalır) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Path kontrolü (En katı kural)
        if kwargs.get('admin_path') != get_daily_admin_path():
            # Eğer path yanlışsa, oturum açılmış olsa bile 404 döndür.
            # Kesinlikle yönlendirme yok!
            abort(404)
        
        # 2. Oturum Kontrolü
        if 'admin_logged_in' not in session:
            # Oturum yoksa, gelen *doğru* dinamik path'in login sayfasına yönlendir.
            return redirect(url_for('admin_login_route', admin_path=kwargs.get('admin_path')))
            
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES: PUBLIC (Aynı kalır) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/words', methods=['GET'])
def get_words():
    # Sadece onaylıları göster
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
        else:
            new_like = UserLike(ip_address=client_ip, word_id=word_id)
            db.session.add(new_like) 
            action = 'liked'
            
        db.session.commit()
        return jsonify({'success': True, 'action': action, 'new_likes': word_to_update.liked_by.count(), 'word_id': word_id})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Sunucu hatası.'}), 500

@app.route('/api/add', methods=['POST'])
def add_word():
    ip = get_client_ip()
    current_time = time.time()
    
    if ip in user_last_post_time and (current_time - user_last_post_time.get(ip, 0) < 30):
        return jsonify({'success': False, 'error': 'Çok hızlı gönderiyorsunuz. Lütfen bekleyin.'}), 429
    
    data = request.get_json()
    word = data.get('word', '').strip()
    definition = data.get('definition', '').strip()
    nickname = data.get('nickname', '').strip()

    if not word or not ALPHANUM_WITH_SPACES.match(word): return jsonify({'success': False, 'error': 'Geçersiz sözcük.'}), 400
    if not definition or not ALPHANUM_WITH_SPACES.match(definition): return jsonify({'success': False, 'error': 'Geçersiz tanım.'}), 400
    if nickname and not ALPHANUM_WITH_SPACES.match(nickname): return jsonify({'success': False, 'error': 'Geçersiz isim.'}), 400

    if not nickname: nickname = 'Anonymous'
    if len(word) > 50 or len(definition) > 300 or len(nickname) > 20:
        return jsonify({'success': False, 'error': 'Metin çok uzun.'}), 400

    try:
        new_word = Word(
            word=html.escape(word),
            definition=html.escape(definition),
            author=html.escape(nickname),
            status='pending' 
        )
        db.session.add(new_word)
        db.session.commit()
        user_last_post_time[ip] = time.time()
        return jsonify({'success': True})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Sunucu hatası.'}), 500

@app.route('/api/comment/add', methods=['POST'])
def add_comment():
    ip = get_client_ip()
    current_time = time.time()
    if ip in user_last_comment_time and (current_time - user_last_comment_time.get(ip, 0) < 30):
        return jsonify({'success': False, 'error': 'Çok hızlı yorum yapıyorsunuz.'}), 429
    
    data = request.get_json()
    word_id = data.get('word_id')
    comment_text = data.get('comment', '').strip()
    author = data.get('author', 'Anonim').strip()

    if not word_id or not comment_text: return jsonify({'success': False, 'error': 'Eksik veri.'}), 400
    if len(comment_text) > 200: return jsonify({'success': False, 'error': 'Yorum çok uzun.'}), 400

    if not db.session.get(Word, word_id): return jsonify({'success': False, 'error': 'Sözcük bulunamadı.'}), 404

    try:
        new_comment = Comment(
            word_id=word_id,
            author=html.escape(author)[:50],
            comment=html.escape(comment_text)
        )
        db.session.add(new_comment)
        db.session.commit()
        user_last_comment_time[ip] = current_time
        return jsonify({'success': True, 'comment': new_comment.to_dict()}), 201
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Hata oluştu.'}), 500

@app.route('/api/comments/<int:word_id>', methods=['GET'])
def get_comments(word_id):
    comments = Comment.query.filter_by(word_id=word_id).order_by(Comment.timestamp.asc()).all()
    return jsonify({'success': True, 'comments': [c.to_dict() for c in comments]})

# --- ROUTES: ADMIN PANEL (Sadece Dinamik URL'ler) ---

@app.route('/<string:admin_path>/login', methods=['GET', 'POST'], endpoint='admin_login_route')
def admin_login(admin_path):
    # 🚨 GÜVENLİK KONTROLÜ: Path doğru değilse, hemen 404 döndür.
    if admin_path != get_daily_admin_path():
        abort(404) 

    if request.method == 'POST':
        password_input = request.form.get('password')
        
        # ----------------------------------------------------
        # GÜVENLİ KONTROL: Şifreleri hash'lenmiş olarak karşılaştır
        # ----------------------------------------------------
        if check_password_hash(ADMIN_PASSWORD_HASH, password_input):
            session['admin_logged_in'] = True
            # Path doğruysa, admin paneline yönlendir
            return redirect(url_for('admin_panel_route', admin_path=admin_path))
        else:
            flash("Hatalı şifre!", "error")
            
    return render_template('admin_login.html')

@app.route('/<string:admin_path>/logout', endpoint='admin_logout_route')
def admin_logout(admin_path):
    # 🚨 GÜVENLİK KONTROLÜ: Path doğru değilse, hemen 404 döndür.
    if admin_path != get_daily_admin_path():
        abort(404) 
        
    session.pop('admin_logged_in', None)
    # Çıkış yaptıktan sonra, sadece doğru dinamik path'teki login sayfasına yönlendirilir.
    return redirect(url_for('admin_login_route', admin_path=get_daily_admin_path()))

@app.route('/<string:admin_path>', endpoint='admin_panel_route')
@login_required # Bu decorator path'i kontrol etmiyordu, şimdi sadece oturumu kontrol ediyor.
def admin_panel(admin_path):
    # 🚨 GÜVENLİK KONTROLÜ: Path doğru değilse, hemen 404 döndür (login_required içinde de var ama burada açıkça belirtelim).
    if admin_path != get_daily_admin_path():
        abort(404) 
        
    # Oturum kontrolü login_required tarafından yapılır.
    
    # Bekleyenler (En yeniden eskiye)
    pending_words = Word.query.filter_by(status='pending').order_by(Word.timestamp.desc()).all()
    # Onaylılar (En yeniden eskiye)
    approved_words = Word.query.filter_by(status='approved').order_by(Word.timestamp.desc()).all()
    
    # Template'e dinamik path'i gönder
    return render_template('admin.html', pending=pending_words, approved=approved_words, admin_path=admin_path)

# --- ROUTES: ADMIN API ACTIONS (Dinamik URL'ler) ---
# Tüm API rotaları sadece doğru path'ten geliyorsa çalışır.

@app.route('/<string:admin_path>/api/admin/approve/<int:word_id>', methods=['POST'], endpoint='admin_approve_route')
@login_required
def admin_approve(admin_path, word_id):
    # Path kontrolü login_required içinde yapıldı.
        
    word = db.session.get(Word, word_id)
    if word:
        word.status = 'approved'
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Bulunamadı'}), 404

@app.route('/<string:admin_path>/api/admin/delete/<int:word_id>', methods=['POST', 'DELETE'], endpoint='admin_delete_route')
@login_required
def admin_delete(admin_path, word_id):
    # Path kontrolü login_required içinde yapıldı.
        
    word = db.session.get(Word, word_id)
    if word:
        db.session.delete(word)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Bulunamadı'}), 404

@app.route('/<string:admin_path>/api/admin/comment/delete/<int:comment_id>', methods=['POST', 'DELETE'], endpoint='admin_delete_comment_route')
@login_required
def admin_delete_comment(admin_path, comment_id):
    # Path kontrolü login_required içinde yapıldı.
        
    comment = db.session.get(Comment, comment_id)
    if comment:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Bulunamadı'}), 404

@app.route('/<string:admin_path>/api/admin/comments/<int:word_id>', methods=['GET'], endpoint='admin_get_comments_route')
@login_required
def admin_get_comments(admin_path, word_id):
    # Path kontrolü login_required içinde yapıldı.
        
    comments = Comment.query.filter_by(word_id=word_id).order_by(Comment.timestamp.asc()).all()
    return jsonify({'success': True, 'comments': [c.to_dict() for c in comments]})

if __name__ == '__main__':
    with app.app_context():
        # 🚩 Düzeltme 3: models.py'daki create_tables kaldırıldı. Doğrudan
        # app.py'da import edilen ve app'e bağlanan db nesnesini kullanıyoruz.
        db.create_all() 
        
        # Başlangıçta dinamik URL'yi yazdırma
        print("\n" + "="*50)
        print("BUGÜNÜN DİNAMİK ADMİN GİRİŞ ADRESİ:")
        print(f"http://127.0.0.1:{PORT}/{get_daily_admin_path()}/login")
        print("="*50 + "\n")
    app.run(debug=True, port=PORT)