from flask import Flask, render_template, request, jsonify
import os
import time
import html
from threading import Lock
  


##
app = Flask(__name__)
# The public dictionary
WORDS_FILE = 'words.txt'
# The holding area
SUBMISSIONS_FILE = 'submissions.txt'

# Locks for thread safety
file_lock = Lock()
user_last_post_time = {} 

# Ensure files exist
for f in [WORDS_FILE, SUBMISSIONS_FILE]:
    if not os.path.exists(f):
        open(f, 'w').close()

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

def read_words():
    words_list = []
    try:
        with open(WORDS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in reversed(lines): 
                if ':' in line:
                    # UPDATED: Split into max 3 parts (Word : Def : Author)
                    parts = line.strip().split(':', 2)
                    word = parts[0].strip()
                    definition = parts[1].strip()
                    # Handle existing words that might not have an author yet
                    author = parts[2].strip() if len(parts) > 2 else ""
                    
                    if word and definition:
                        words_list.append({
                            'word': word, 
                            'def': definition,
                            'author': author
                        })
    except Exception as e:
        print(f"Error reading file: {e}")
    return words_list

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/words', methods=['GET'])
def get_words():
    return jsonify(read_words())

@app.route('/api/add', methods=['POST'])
def add_word():
    # --- RATE LIMIT ---
    client_ip = get_client_ip()
    current_time = time.time()
    
    if client_ip in user_last_post_time:
        last_time = user_last_post_time[client_ip]
        if current_time - last_time < 5: 
            return jsonify({'success': False, 'error': 'Please wait 5 seconds.'}), 429
    
    user_last_post_time[client_ip] = current_time

    # --- PROCESSING ---
    data = request.json
    word = data.get('word', '')
    definition = data.get('definition', '')
    # UPDATED: Get the nickname
    nickname = data.get('nickname', 'Anonymous')
    
    if len(word) > 50 or len(definition) > 300 or len(nickname) > 20:
        return jsonify({'success': False, 'error': 'Text too long.'}), 400
    
    if word and definition:
        clean_word = html.escape(word).replace('\n', ' ').replace(':', '-')
        clean_def = html.escape(definition).replace('\n', ' ').replace(':', '-')
        clean_nick = html.escape(nickname).replace('\n', ' ').replace(':', '-')
        
        # WRITE TO SUBMISSIONS.TXT (Word:Def:Nick)
        with file_lock:
            with open(SUBMISSIONS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{clean_word}:{clean_def}:{clean_nick}\n")
        
        return jsonify({'success': True, 'message': 'Word submitted for review!'})
    
    return jsonify({'success': False, 'error': 'Missing data'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)