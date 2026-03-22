import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_socketio import SocketIO, send, join_room, leave_room, emit
import sqlite3
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

import datetime

# Define database paths relative to the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL_DB_PATH = os.path.join(BASE_DIR, 'social_system.db')
FEEDBACK_DB_PATH = os.path.join(BASE_DIR, 'feedback.db')

import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key' 
socketio = SocketIO(app)

# --- Global Variables ---
user_to_sid = {}
sid_to_user = {}
disconnect_timers = {}

# --- Database Initialization ---
def initialize_database():
    conn = sqlite3.connect(SOCIAL_DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            meal_purpose TEXT NOT NULL,
            gender TEXT NOT NULL,
            personality TEXT NOT NULL,
            interest1 TEXT NOT NULL,
            interest2 TEXT,
            interest3 TEXT,
            chat_preference TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            matched_with_id INTEGER,
            contact_method TEXT NOT NULL,
            contact_id TEXT NOT NULL
        )''')
    conn.commit()
    conn.close()

def initialize_feedback_database():
    conn = sqlite3.connect(FEEDBACK_DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY,
            rater_id INTEGER NOT NULL,
            rated_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            gmail TEXT,
            feedback_text TEXT,
            timestamp TEXT NOT NULL,
            wants_contact_exchange INTEGER DEFAULT 0
        )''')
    # 若舊表無 wants_contact_exchange 欄位則補上
    c.execute("PRAGMA table_info(ratings)")
    cols = [row[1] for row in c.fetchall()]
    if 'wants_contact_exchange' not in cols:
        c.execute("ALTER TABLE ratings ADD COLUMN wants_contact_exchange INTEGER DEFAULT 0")
    c.execute('''CREATE TABLE IF NOT EXISTS contact_exchange_pending (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            partner_contact_display TEXT NOT NULL,
            created_at TEXT NOT NULL
        )''')
    c.execute('''CREATE TABLE IF NOT EXISTS contact_submitted_cache (
            user_id INTEGER PRIMARY KEY,
            contact_method TEXT NOT NULL,
            contact_id TEXT NOT NULL
        )''')
    conn.commit()
    conn.close()

initialize_database()
initialize_feedback_database()

from social_agent import SocialAgent

# --- Gemini Agent Initialization ---
agent = SocialAgent(api_key=os.environ.get("GEMINI_API_KEY"))


# --- Disconnect Handling Function (Critical Modification) ---
def handle_final_disconnect(user_id):
    """
    Execute this function after the user disconnect buffer period ends.
    """
    print(f"使用者 {user_id} 的緩衝期已到，執行最終清理...")
    with app.test_request_context():
        conn = sqlite3.connect(SOCIAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Find out who the disconnected user's partner is
        c.execute("SELECT matched_with_id FROM users WHERE id = ?", (user_id,))
        result = c.fetchone()
        
        # Clean up tracking dictionary
        sid = user_to_sid.pop(user_id, None)
        if sid:
            sid_to_user.pop(sid, None)
        disconnect_timers.pop(user_id, None)

        if result and result['matched_with_id']:
            partner_id = result['matched_with_id']
            partner_sid = user_to_sid.get(partner_id)

            # Notify the partner and redirect them to the feedback page
            if partner_sid:
                # Critical modification: Send force_feedback event instead of partner_disconnected
                socketio.emit('force_feedback', {
                    'message': '您的夥伴已斷線，請您完成最終的評分。',
                    'redirect_url': url_for('feedback_page', rater_id=partner_id, rated_id=user_id)
                }, room=partner_sid)
                print(f"已強制使用者 {partner_id} 跳轉至評分頁面，因為夥伴 {user_id} 已斷線")
            
            # Backup contact metadata to feedback db before deletion
            conn_fb = sqlite3.connect(FEEDBACK_DB_PATH)
            c_fb = conn_fb.cursor()
            for uid in (user_id, partner_id):
                c.execute("SELECT contact_method, contact_id FROM users WHERE id = ?", (uid,))
                row = c.fetchone()
                if row:
                    c_fb.execute("INSERT OR REPLACE INTO contact_submitted_cache (user_id, contact_method, contact_id) VALUES (?, ?, ?)", (uid, row['contact_method'], row['contact_id']))
            conn_fb.commit()
            conn_fb.close()

            # Preserve data for historical records using status 'left'
            c.execute("UPDATE users SET status = 'left' WHERE id = ?", (user_id,))
            c.execute("UPDATE users SET status = 'left' WHERE id = ?", (partner_id,))
        else:
             # If the user disconnects before matching, update status to 'left'
             c.execute("UPDATE users SET status = 'left' WHERE id = ?", (user_id,))

        conn.commit()
        conn.close()

# --- SocketIO Events ---
@socketio.on('join')
def on_join(data):
    user_id = data['user_id']
    sid = request.sid
    if user_id in disconnect_timers:
        disconnect_timers[user_id].cancel()
        disconnect_timers.pop(user_id)
        print(f"使用者 {user_id} 在緩衝期內重連，已取消清理程序。")
    user_to_sid[user_id] = sid
    sid_to_user[sid] = user_id
    print(f"使用者 {user_id} 加入，SID 為 {sid}")

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    user_id = sid_to_user.get(sid)
    if user_id:
        print(f"使用者 {user_id} (SID: {sid}) 斷線，啟動 5 秒緩衝計時器。")
        timer = threading.Timer(5.0, handle_final_disconnect, args=[user_id])
        disconnect_timers[user_id] = timer
        timer.start()

@socketio.on('message')
def handle_message(data):
    sender_id = sid_to_user.get(request.sid)
    if not sender_id: return
    with app.app_context():
        conn = sqlite3.connect(SOCIAL_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT matched_with_id FROM users WHERE id = ?", (sender_id,))
        result = c.fetchone()
        conn.close()
        if result and result[0]:
            partner_id = result[0]
            sender_sid = user_to_sid.get(sender_id)
            partner_sid = user_to_sid.get(partner_id)
            if sender_sid: emit('message', data, room=sender_sid)
            if partner_sid: emit('message', data, room=partner_sid)

# --- Routes (Except for submit_feedback, others remain unchanged) ---
@app.route('/')
@app.route('/home')
def home():
    pending_contact_method = None
    pending_contact_id = None
    anon_id = session.get('anon_user_id')
    if anon_id:
        conn = sqlite3.connect(FEEDBACK_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT partner_contact_display FROM contact_exchange_pending WHERE user_id=? LIMIT 1", (anon_id,))
        row = c.fetchone()
        if row:
            raw = row[0]
            if '|' in raw:
                parts = raw.split('|', 1)
                pending_contact_method, pending_contact_id = parts[0], parts[1]
            c.execute("DELETE FROM contact_exchange_pending WHERE user_id=?", (anon_id,))
            conn.commit()
        conn.close()
        if pending_contact_method and pending_contact_id:
            session.pop('anon_user_id', None)
    return render_template('index.html', pending_contact_method=pending_contact_method, pending_contact_id=pending_contact_id)

@app.route('/about')
def about():
    info_path = os.path.join(BASE_DIR, 'src', 'info.json')
    with open(info_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return render_template('about.html', authors=data["authors"], site_description=data["site_description"])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get data from the registration form
        meal_purpose = request.form.get('meal_purpose')
        gender = request.form.get('gender')
        personality = request.form.get('personality')
        chat_preference = request.form.get('chat_preference')
        contact_method = request.form.get('contact_method')
        contact_id = request.form.get('contact_id')
        
        # 處理 checkbox 傳來的 interests list
        interests = request.form.getlist('interests')
        interest1 = interests[0] if len(interests) > 0 else ''
        interest2 = interests[1] if len(interests) > 1 else ''
        interest3 = interests[2] if len(interests) > 2 else ''

        if not all([meal_purpose, gender, personality, interest1, chat_preference, contact_method, contact_id]):
            return "錯誤：所有必填欄位都必須填寫！", 400
        conn = sqlite3.connect(SOCIAL_DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO users (meal_purpose, gender, personality, interest1, interest2, interest3, chat_preference, contact_method, contact_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (meal_purpose, gender, personality, interest1, interest2, interest3, chat_preference, contact_method, contact_id))
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        return redirect(url_for('submission_success', user_id=user_id))
    return render_template('register.html')

@app.route('/success/<int:user_id>')
def submission_success(user_id):
    return render_template('submission_success.html', user_id=user_id)

@app.route('/chat/<int:user_id>')
def chat_room(user_id):
    conn = sqlite3.connect(SOCIAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    current_user = c.fetchone()
    if not current_user:
        conn.close()
        return redirect(url_for('home'))
        
    matched_user = None
    if current_user['status'] == 'in_chat' and current_user['matched_with_id']:
        c.execute("SELECT * FROM users WHERE id = ?", (current_user['matched_with_id'],))
        matched_user = c.fetchone()
    elif current_user['status'] == 'available':
        # If the user is still available, they should not be in the chat room yet.
        # Redirect them back to the success page to wait for a match.
        conn.close()
        return redirect(url_for('submission_success', user_id=user_id))
    
    greeting, shared_topics, user1_topics, user2_topics = "", "正在生成話題...", "", ""
    user1_name, user2_name = "", ""
    if matched_user:
        user1_name = f"夥伴 #{current_user['id']}"
        user2_name = f"夥伴 #{matched_user['id']}"
        # Generate interests strings for the AI prompt
        current_user_interests = ", ".join(filter(None, [current_user['interest1'], current_user['interest2'], current_user['interest3']]))
        matched_user_interests = ", ".join(filter(None, [matched_user['interest1'], matched_user['interest2'], matched_user['interest3']]))
        # Call the AI agent to generate conversation topics
        raw_response = agent.generate_topics(user1_name, current_user_interests, user2_name, matched_user_interests)
        print(f"DEBUG_AI_RESPONSE: {raw_response}")
        # Parse the JSON response from the AI
        try:
            ai_data = json.loads(raw_response)
            greeting = ai_data.get("greeting", "").replace('\n', '<br>')
            shared_topics_list = ai_data.get("shared_topics", [])
            user1_topics_list = ai_data.get("user1_topics", [])
            user2_topics_list = ai_data.get("user2_topics", [])
            
            # Format lists into HTML strings
            shared_topics = "<br>".join(shared_topics_list)
            user1_topics = "<br>".join(user1_topics_list)
            user2_topics = "<br>".join(user2_topics_list)
        except json.JSONDecodeError:
            print(f"Error parsing JSON: {raw_response}")
            shared_topics = "Error generating topics. Please try again."
    conn.close()
    return render_template('chat.html', current_user=current_user, matched_user=matched_user, greeting=greeting, shared_topics=shared_topics, user1_topics=user1_topics, user2_topics=user2_topics, user1_name=user1_name, user2_name=user2_name)

@app.route('/feedback/<int:rater_id>/<int:rated_id>')
def feedback_page(rater_id, rated_id):
    session['anon_user_id'] = rater_id  # 用於首頁檢查待領取聯絡方式
    return render_template('feedback.html', rater_id=rater_id, rated_id=rated_id)

@app.route('/api/express_exchange_intent/<int:rater_id>/<int:rated_id>', methods=['POST'])
def express_exchange_intent(rater_id, rated_id):
    data = request.get_json() or {}
    wants_exchange = int(data.get('wants_exchange', 1))
    
    conn = sqlite3.connect(FEEDBACK_DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS exchange_intents (rater_id INTEGER, rated_id INTEGER, wants_exchange INTEGER, timestamp TEXT, PRIMARY KEY (rater_id, rated_id))")
    c.execute("INSERT OR REPLACE INTO exchange_intents (rater_id, rated_id, wants_exchange, timestamp) VALUES (?, ?, ?, ?)", 
              (rater_id, rated_id, wants_exchange, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/contact_exchange_status/<int:rater_id>/<int:rated_id>')
def api_contact_exchange_status(rater_id, rated_id):
    """查詢對方是否已經同意交換。"""
    conn_fb = sqlite3.connect(FEEDBACK_DB_PATH)
    c_fb = conn_fb.cursor()
    c_fb.execute("SELECT wants_contact_exchange FROM ratings WHERE rater_id=? AND rated_id=?", (rated_id, rater_id))
    partner_rating = c_fb.fetchone()
    
    c_fb.execute("CREATE TABLE IF NOT EXISTS exchange_intents (rater_id INTEGER, rated_id INTEGER, wants_exchange INTEGER, timestamp TEXT, PRIMARY KEY (rater_id, rated_id))")
    c_fb.execute("SELECT wants_exchange FROM exchange_intents WHERE rater_id=? AND rated_id=?", (rated_id, rater_id))
    partner_intent = c_fb.fetchone()
    conn_fb.close()

    agreed = False
    declined = False
    
    if partner_rating:
        if partner_rating[0] == 1:
            agreed = True
        else:
            declined = True
    elif partner_intent:
        if partner_intent[0] == 1:
            agreed = True
        else:
            declined = True
            
    if declined:
        return jsonify({
            "status": "declined",
            "message": "對方比較害羞，期待後續你們還有機會遇見！"
        })
        
    if agreed:
        def get_contact(uid):
            conn_u = sqlite3.connect(SOCIAL_DB_PATH)
            conn_u.row_factory = sqlite3.Row
            c_u = conn_u.cursor()
            c_u.execute("SELECT contact_method, contact_id FROM users WHERE id=?", (uid,))
            r = c_u.fetchone()
            conn_u.close()
            if r: return r['contact_method'], r['contact_id']
            
            conn_f = sqlite3.connect(FEEDBACK_DB_PATH)
            c_f = conn_f.cursor()
            c_f.execute("SELECT contact_method, contact_id FROM contact_submitted_cache WHERE user_id=?", (uid,))
            r = c_f.fetchone()
            conn_f.close()
            if r: return r[0], r[1]
            return None, None
            
        method, cid = get_contact(rated_id)
        if method:
            return jsonify({
                "status": "agreed",
                "message": "你們都同意交換聯絡方式！",
                "partner_contact_method": method,
                "partner_contact_id": cid
            })
            
    return jsonify({"status": "waiting", "message": "正在等待對方回應..."})

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    rater_id = int(request.form.get('rater_id'))
    rated_id = int(request.form.get('rated_id'))
    wants_exchange = int(request.form.get('wants_contact_exchange', 0))
    
    # Notify Partner
    partner_sid = user_to_sid.get(rated_id)
    if partner_sid:
        socketio.emit('force_feedback', {
            'message': '對方已結束聊天，請您也完成評分。',
            'redirect_url': url_for('feedback_page', rater_id=rated_id, rated_id=rater_id)
        }, room=partner_sid)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rating = request.form.get('rating')
    gmail = request.form.get('gmail')
    feedback_text = request.form.get('feedback_text')
    
    # 在刪除 users 前先查詢雙方聯絡方式（若雙方都同意交換）
    partner_contact_display = None
    conn_users = sqlite3.connect(SOCIAL_DB_PATH)
    conn_users.row_factory = sqlite3.Row
    c_users = conn_users.cursor()
    
    conn_feedback = sqlite3.connect(FEEDBACK_DB_PATH)
    c_feedback = conn_feedback.cursor()
    c_feedback.execute(
        "SELECT wants_contact_exchange FROM ratings WHERE rater_id=? AND rated_id=?",
        (rated_id, rater_id)
    )
    partner_rating = c_feedback.fetchone()
    
    def get_contact(uid):
        c_users.execute("SELECT contact_method, contact_id FROM users WHERE id=?", (uid,))
        r = c_users.fetchone()
        if r: return r['contact_method'], r['contact_id']
        c_feedback.execute("SELECT contact_method, contact_id FROM contact_submitted_cache WHERE user_id=?", (uid,))
        r = c_feedback.fetchone()
        if r: return r[0], r[1]
        return None, None

    # 若本人願意交換，在刪除前先存聯絡方式到快取（供對方稍後查詢）
    if wants_exchange:
        my_method, my_cid = get_contact(rater_id)
        if my_method:
            c_feedback.execute(
                "INSERT OR REPLACE INTO contact_submitted_cache (user_id, contact_method, contact_id) VALUES (?, ?, ?)",
                (rater_id, my_method, my_cid)
            )

    # 儲存評分
    c_feedback.execute(
        '''INSERT INTO ratings (rater_id, rated_id, rating, gmail, feedback_text, timestamp, wants_contact_exchange)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (rater_id, rated_id, rating, gmail, feedback_text, timestamp, wants_exchange)
    )
    conn_feedback.commit()
    conn_feedback.close()
    
    # 將狀態改為已完成，永久保留資料
    conn_users_norm = sqlite3.connect(SOCIAL_DB_PATH)
    c_del = conn_users_norm.cursor()
    c_del.execute("UPDATE users SET status = 'finished' WHERE id = ?", (rater_id,))
    c_del.execute("UPDATE users SET status = 'finished' WHERE id = ?", (rated_id,))
    conn_users_norm.commit()
    conn_users_norm.close()
    conn_users.close()
    
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
        if username == admin_username and password == admin_password:
            session['logged_in'] = True
            flash('登入成功！', 'success')
            return redirect(url_for('admin'))
        else:
            flash('密碼錯誤，請重試。', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('已登出。', 'info')
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(SOCIAL_DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT * FROM users''')
    user_list = c.fetchall()
    conn.close()
    return render_template('admin.html', user_list=user_list)

@app.route('/admin/feedback')
def admin_feedback():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(FEEDBACK_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM ratings ORDER BY timestamp DESC")
    feedback_list = c.fetchall()
    conn.close()
    return render_template('admin_feedback.html', feedback_list=feedback_list)

@app.route('/api/check_match/<int:user_id>')
def check_match_status(user_id):
    conn = sqlite3.connect(SOCIAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT status FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user and user['status'] == 'in_chat':
        return jsonify({'matched': True})
    return jsonify({'matched': False})

@app.route('/api/try_match/<int:user_id>')
def api_try_match(user_id):
    conn = sqlite3.connect(SOCIAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Fetch current user
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    current_user = c.fetchone()
    
    if not current_user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
        
    matched_user = None
    
    # 2. Check if already matched
    if current_user['status'] == 'in_chat' and current_user['matched_with_id']:
        c.execute("SELECT * FROM users WHERE id = ?", (current_user['matched_with_id'],))
        matched_user = c.fetchone()
        
    # 3. If available, try matching right now
    elif current_user['status'] == 'available':
        query = "SELECT * FROM users WHERE id != ? AND status = 'available' AND (chat_preference = ? OR chat_preference = 'any') AND (? = 'any' OR gender = ?) ORDER BY RANDOM() LIMIT 1"
        params = (user_id, current_user['gender'], current_user['chat_preference'], current_user['chat_preference'])
        c.execute(query, params)
        matched_user = c.fetchone()
        
        if matched_user:
            # Pair users and update status
            c.execute("UPDATE users SET status = 'in_chat', matched_with_id = ? WHERE id = ?", (matched_user['id'], current_user['id']))
            c.execute("UPDATE users SET status = 'in_chat', matched_with_id = ? WHERE id = ?", (current_user['id'], matched_user['id']))
            conn.commit()

    conn.close()
    
    # 4. Process match data if match exists
    if matched_user:
        # Calculate shared interests
        curr_interests = {current_user['interest1'], current_user['interest2'], current_user['interest3']}
        match_interests = {matched_user['interest1'], matched_user['interest2'], matched_user['interest3']}
        # Remove empty strings
        curr_interests.discard('')
        curr_interests.discard(None)
        match_interests.discard('')
        match_interests.discard(None)
        
        shared_interests = list(curr_interests.intersection(match_interests))
        if not shared_interests:
            # Fallback if no exact string match (unlikely if they came from identical checkboxes, but safe fallback)
            shared_interests = [list(match_interests)[0]] if match_interests else ["聊天"]
            
        # Map personality keys to friendly terms
        personality_map = {
            'very_extrovert': '非常外向 (E)',
            'extrovert': '外向 (偏E)',
            'introvert': '內向 (偏I)',
            'very_introvert': '非常內向 (I)'
        }
        partner_personality = personality_map.get(matched_user['personality'], '好相處')
        
        return jsonify({
            'matched': True,
            'shared_interests': shared_interests,
            'partner_personality': partner_personality
        })
        
    return jsonify({'matched': False})

if __name__ == '__main__':
    socketio.run(app, debug=True)