import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_socketio import SocketIO, send, join_room, leave_room, emit
import sqlite3
import json
import os
import re

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
    conn = sqlite3.connect('social_system.db', check_same_thread=False)
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
            matched_with_id INTEGER
        )''')
    conn.commit()
    conn.close()

def initialize_feedback_database():
    conn = sqlite3.connect('feedback.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY,
            rater_id INTEGER NOT NULL,
            rated_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            gmail TEXT,
            feedback_text TEXT,
            timestamp TEXT NOT NULL
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
        conn = sqlite3.connect('social_system.db')
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
            
            # Delete data for both parties from the database
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))
            c.execute("DELETE FROM users WHERE id = ?", (partner_id,))
        else:
             # If the user disconnects before matching, just delete themselves
             c.execute("DELETE FROM users WHERE id = ?", (user_id,))

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
        conn = sqlite3.connect('social_system.db')
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
    return render_template('index.html')

@app.route('/about')
def about():
    with open('./src/info.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return render_template('about.html', authors=data["authors"], site_description=data["site_description"])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get data from the registration form
        meal_purpose = request.form.get('meal_purpose')
        gender = request.form.get('gender')
        personality = request.form.get('personality')
        interest1 = request.form.get('interest1')
        interest2 = request.form.get('interest2', '')
        interest3 = request.form.get('interest3', '')
        chat_preference = request.form.get('chat_preference')
        if not all([meal_purpose, gender, personality, interest1, chat_preference]):
            return "錯誤：所有必填欄位都必須填寫！", 400
        conn = sqlite3.connect('social_system.db')
        c = conn.cursor()
        c.execute('''INSERT INTO users (meal_purpose, gender, personality, interest1, interest2, interest3, chat_preference)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (meal_purpose, gender, personality, interest1, interest2, interest3, chat_preference))
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
    conn = sqlite3.connect('social_system.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    current_user = c.fetchone()
    if not current_user:
        conn.close()
        return redirect(url_for('home'))
    matched_user = None
    if current_user['status'] == 'in_chat':
        if current_user['matched_with_id']:
            c.execute("SELECT * FROM users WHERE id = ?", (current_user['matched_with_id'],))
            matched_user = c.fetchone()
    elif current_user['status'] == 'available':
        query = "SELECT * FROM users WHERE id != ? AND status = 'available' AND (chat_preference = ? OR chat_preference = 'any') AND (? = 'any' OR gender = ?) ORDER BY RANDOM() LIMIT 1"
        params = (user_id, current_user['gender'], current_user['chat_preference'], current_user['chat_preference'])
        c.execute(query, params)
        matched_user = c.fetchone()
        if matched_user:
            # Pair users and update their status to 'in_chat'
            c.execute("UPDATE users SET status = 'in_chat', matched_with_id = ? WHERE id = ?", (matched_user['id'], current_user['id']))
            c.execute("UPDATE users SET status = 'in_chat', matched_with_id = ? WHERE id = ?", (current_user['id'], matched_user['id']))
            conn.commit()
    greeting, shared_topics, user1_topics, user2_topics = "", "正在生成話題...", "", ""
    user1_name, user2_name = "", ""
    if matched_user:
        user1_name = f"夥伴{current_user['id']}"
        user2_name = f"夥伴{matched_user['id']}"
        # Generate interests strings for the AI prompt
        current_user_interests = ", ".join(filter(None, [current_user['interest1'], current_user['interest2'], current_user['interest3']]))
        matched_user_interests = ", ".join(filter(None, [matched_user['interest1'], matched_user['interest2'], matched_user['interest3']]))
        # Call the AI agent to generate conversation topics
        raw_response = agent.generate_topics(user1_name, current_user_interests, user2_name, matched_user_interests)
        print(f"DEBUG_AI_RESPONSE: {raw_response}")
        # Parse the AI response using Regex to extract specific sections
        greeting_match = re.search(r'\[GREETING\]\s*(.*?)\s*\[SHARED\]', raw_response, re.DOTALL)
        shared_match = re.search(r'\[SHARED\]\s*(.*?)\s*\[FOR_', raw_response, re.DOTALL)
        user1_match = re.search(rf'\[FOR_{user1_name}\]\s*(.*?)\s*\[FOR_{user2_name}\]', raw_response, re.DOTALL)
        user2_match = re.search(rf'\[FOR_{user2_name}\]\s*(.*)', raw_response, re.DOTALL)
        if greeting_match: greeting = greeting_match.group(1).strip().replace('\n', '<br>')
        if shared_match: shared_topics = shared_match.group(1).strip().replace('\n', '<br>')
        if user1_match: user1_topics = user1_match.group(1).strip().replace('\n', '<br>')
        if user2_match: user2_topics = user2_match.group(1).strip().replace('\n', '<br>')

        # If parsing fails and an error message is returned, show the error
        if "呼叫 API 時發生錯誤" in raw_response:
             shared_topics = raw_response
    conn.close()
    return render_template('chat.html', current_user=current_user, matched_user=matched_user, greeting=greeting, shared_topics=shared_topics, user1_topics=user1_topics, user2_topics=user2_topics, user1_name=user1_name, user2_name=user2_name)

@app.route('/feedback/<int:rater_id>/<int:rated_id>')
def feedback_page(rater_id, rated_id):
    return render_template('feedback.html', rater_id=rater_id, rated_id=rated_id)

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    rater_id = int(request.form.get('rater_id'))
    rated_id = int(request.form.get('rated_id'))
    
    # Notify Partner
    partner_sid = user_to_sid.get(rated_id)
    if partner_sid:
        socketio.emit('force_feedback', {
            'message': '對方已結束聊天，請您也完成評分。',
            'redirect_url': url_for('feedback_page', rater_id=rated_id, rated_id=rater_id)
        }, room=partner_sid)
    
    # Save Rating
    rating = request.form.get('rating')
    gmail = request.form.get('gmail')
    feedback_text = request.form.get('feedback_text')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn_feedback = sqlite3.connect('feedback.db')
    c_feedback = conn_feedback.cursor()
    c_feedback.execute('''INSERT INTO ratings (rater_id, rated_id, rating, gmail, feedback_text, timestamp)
                          VALUES (?, ?, ?, ?, ?, ?)''', 
                         (rater_id, rated_id, rating, gmail, feedback_text, timestamp))
    conn_feedback.commit()
    conn_feedback.close()
    
    # Delete User
    conn_users = sqlite3.connect('social_system.db')
    c_users = conn_users.cursor()
    c_users.execute("DELETE FROM users WHERE id = ?", (rater_id,))
    c_users.execute("DELETE FROM users WHERE id = ?", (rated_id,))
    conn_users.commit()
    conn_users.close()
    
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        # Simple password verification, use environment variables recommended
        admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
        if password == admin_password:
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
    conn = sqlite3.connect('social_system.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM users''')
    user_list = c.fetchall()
    conn.close()
    return render_template('admin.html', user_list=user_list)

@app.route('/admin/feedback')
def admin_feedback():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('feedback.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM ratings ORDER BY timestamp DESC")
    feedback_list = c.fetchall()
    conn.close()
    return render_template('admin_feedback.html', feedback_list=feedback_list)

@app.route('/api/check_match/<int:user_id>')
def check_match_status(user_id):
    conn = sqlite3.connect('social_system.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT status FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user and user['status'] == 'in_chat':
        return jsonify({"status": "matched", "redirect_url": url_for('chat_room', user_id=user_id)})
    else:
        return jsonify({"status": "waiting"})

if __name__ == '__main__':
    socketio.run(app, debug=True)