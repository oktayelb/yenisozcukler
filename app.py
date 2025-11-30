from flask import Flask, render_template, request, jsonify
import os
import time
import html
from threading import Lock
import re

app = Flask(__name__)

WORDS_FILE = 'words.txt'
SUBMISSIONS_FILE = 'submissions.txt'
PORT = 5000

file_lock = Lock()
user_last_post_time = {}

GLOBAL_WORDS_CACHE = []
GLOBAL_TOTAL_COUNT = 0
LAST_MODIFIED_TIME = 0

ALPHANUM_WITH_SPACES = re.compile(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9]*$')

# Ensure files exist
for f in [WORDS_FILE, SUBMISSIONS_FILE]:
    if not os.path.exists(f):
        open(f, 'w').close()

def get_client_ip():
    return request.remote_addr

def update_cache_if_dirty():
    global GLOBAL_WORDS_CACHE, GLOBAL_TOTAL_COUNT, LAST_MODIFIED_TIME

    try:
        current_mtime = os.path.getmtime(WORDS_FILE)
    except OSError:
        return

    if current_mtime <= LAST_MODIFIED_TIME:
        return

    new_list = []
    try:
        with open(WORDS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in reversed(lines):
                if ':' in line:
                    parts = line.strip().split(':', 2)
                    word = parts[0].strip()
                    definition = parts[1].strip()
                    author = parts[2].strip() if len(parts) > 2 else ""

                    if word and definition:
                        new_list.append({
                            'word': word,
                            'def': definition,
                            'author': author
                        })
    except Exception as e:
        print(f"Error initializing cache: {e}")

    GLOBAL_WORDS_CACHE = new_list
    GLOBAL_TOTAL_COUNT = len(new_list)
    LAST_MODIFIED_TIME = current_mtime


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/words', methods=['GET'])
def get_words():
    update_cache_if_dirty()

    all_words = GLOBAL_WORDS_CACHE
    total_count = GLOBAL_TOTAL_COUNT

    # --- FIX: count gelmiyorsa 0 kabul et ---
    raw_count = request.args.get('count', default="0")
    try:
        client_count = int(raw_count)
    except:
        client_count = 0

    # Eğer client'ın bildiği sayı = total_count → yeni bir şey yok → boş liste dön
    if client_count >= total_count:
        return jsonify({
            'words': [],
            'total_count': total_count,
            'status': 'updated'
        })

    # Yeni sözcük sayısı
    new_word_count = total_count - client_count
    new_words = all_words[:new_word_count]

    return jsonify({
        'words': new_words,
        'total_count': total_count,
        'status': 'updated'
    })


@app.route('/api/add', methods=['POST'])
def add_word():
    client_ip = get_client_ip()
    current_time = time.time()

    if client_ip in user_last_post_time:
        last_time = user_last_post_time[client_ip]
        if current_time - last_time < 5:
            return jsonify({'success': False, 'error': 'Lütfen 5 saniye bekleyin.'}), 429

    user_last_post_time[client_ip] = current_time

    data = request.json
    word = data.get('word', '')
    definition = data.get('definition', '')
    nickname = data.get('nickname', '')

    if not word.strip() or not ALPHANUM_WITH_SPACES.match(word.strip()):
        return jsonify({'success': False, 'error': 'Sözcük alanı sadece harf, rakam, boşluk, nokta veya virgül içerebilir.'}), 400

    if nickname and not ALPHANUM_WITH_SPACES.match(nickname):
        return jsonify({'success': False, 'error': 'Takma ad sadece harf, rakam, boşluk, nokta veya virgül içerebilir.'}), 400

    if not definition.strip() or not ALPHANUM_WITH_SPACES.match(definition):
        return jsonify({'success': False, 'error': 'Tanım sadece harf, rakam, boşluk, nokta veya virgül içerebilir.'}), 400

    if not nickname.strip():
        nickname = 'Anonymous'

    if len(word) > 50 or len(definition) > 300 or len(nickname) > 20:
        return jsonify({'success': False, 'error': 'Metin çok uzun.'}), 400

    clean_word = html.escape(word).replace('\n', ' ').replace(':', '-')
    clean_def = html.escape(definition).replace('\n', ' ').replace(':', '-')
    clean_nick = html.escape(nickname).replace('\n', ' ').replace(':', '-')

    with file_lock:
        with open(SUBMISSIONS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{clean_word}:{clean_def}:{clean_nick}\n")

    return jsonify({'success': True, 'message': 'Sözcük inceleme için gönderildi!'})


if __name__ == '__main__':
    update_cache_if_dirty()
    app.run(host='0.0.0.0', port=PORT, debug=False)