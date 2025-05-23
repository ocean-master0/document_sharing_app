from flask import Flask, render_template, request, send_file, jsonify, Response
import sqlite3
import random
import string
import hashlib
from datetime import datetime, timedelta
import io
import os

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                doc_name TEXT NOT NULL,
                user_name TEXT NOT NULL,
                user_id_hash TEXT NOT NULL,
                user_id TEXT NOT NULL,
                code TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS forget_codes
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id_hash TEXT NOT NULL,
                user_id TEXT NOT NULL,
                code TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# Clean up expired entries (older than 7 days)
def cleanup_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    expiration_time = datetime.now() - timedelta(days=7)
    c.execute("DELETE FROM documents WHERE created_at < ?", (expiration_time,))
    c.execute("DELETE FROM forget_codes WHERE created_at < ?", (expiration_time,))
    conn.commit()
    conn.close()

# Hash User ID
def hash_user_id(user_id):
    return hashlib.sha256(user_id.encode()).hexdigest()

# Generate random 10-digit User ID
def generate_user_id():
    return ''.join(random.choices(string.digits, k=10))

# Generate random code
def generate_code(length=4):
    return ''.join(random.choices(string.digits, k=length))

# Check if User ID hash exists
def check_user_id_exists(user_id_hash):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM documents WHERE user_id_hash = ?", (user_id_hash,))
    exists = c.fetchone()[0] > 0
    conn.close()
    return exists

# Delete user and all associated data - ADDED THIS FUNCTION
def delete_user(user_id_hash):
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        # Delete all documents associated with the user
        c.execute("DELETE FROM documents WHERE user_id_hash = ?", (user_id_hash,))
        # Delete all forget codes associated with the user
        c.execute("DELETE FROM forget_codes WHERE user_id_hash = ?", (user_id_hash,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False

# Home route - Upload document
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        doc_name = request.form['doc_name']
        user_name = request.form['user_name']
        custom_user_id = request.form.get('custom_user_id')
        use_custom = request.form.get('use_custom') == 'on'
        
        if url and doc_name and user_name:
            cleanup_db()
            
            user_id = custom_user_id if use_custom and custom_user_id else generate_user_id()
            user_id_hash = hash_user_id(user_id)
            
            if use_custom and check_user_id_exists(user_id_hash):
                return render_template('index.html', error="User ID already exists.")
            
            codes = [generate_code(4) for _ in range(5)]
            forget_codes = [generate_code(6) for _ in range(10)] if not check_user_id_exists(user_id_hash) else None
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            for code in codes:
                c.execute("INSERT INTO documents (url, doc_name, user_name, user_id_hash, user_id, code) VALUES (?, ?, ?, ?, ?, ?)",
                         (url, doc_name, user_name, user_id_hash, user_id, code))
            
            if forget_codes:
                for code in forget_codes:
                    c.execute("INSERT INTO forget_codes (user_id_hash, user_id, code) VALUES (?, ?, ?)",
                             (user_id_hash, user_id, code))
            
            conn.commit()
            conn.close()
            
            return render_template('index.html', codes=codes, forget_codes=forget_codes, url=url, doc_name=doc_name, user_name=user_name, user_id=user_id)
    
    return render_template('index.html')

# Existing User route - UPDATED WITH DELETE ACCOUNT FUNCTIONALITY
@app.route('/existing', methods=['GET', 'POST'])
def existing():
    if request.method == 'POST':
        # Added handler for delete_user action
        if 'delete_user' in request.form:
            user_id = request.form['user_id']
            user_id_hash = hash_user_id(user_id)
            
            if delete_user(user_id_hash):
                return render_template('existing.html', success_message="Your account has been successfully deleted.")
            else:
                return render_template('existing.html', error="An error occurred while deleting your account.")
        
        elif 'user_id' in request.form and 'user_name' in request.form:
            user_id = request.form['user_id']
            user_name = request.form['user_name']
            url = request.form.get('url', '')
            doc_name = request.form.get('doc_name', '')
            user_id_hash = hash_user_id(user_id)
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            c.execute("SELECT id, doc_name, url FROM documents WHERE user_id_hash = ?", (user_id_hash,))
            existing_docs = c.fetchall()
            
            if not existing_docs:
                conn.close()
                return render_template('existing.html', error="User ID does not exist.")
            
            if url and doc_name:
                codes = [generate_code(4) for _ in range(5)]
                for code in codes:
                    c.execute("INSERT INTO documents (url, doc_name, user_name, user_id_hash, user_id, code) VALUES (?, ?, ?, ?, ?, ?)",
                             (url, doc_name, user_name, user_id_hash, user_id, code))
                conn.commit()
                c.execute("SELECT id, doc_name, url FROM documents WHERE user_id_hash = ?", (user_id_hash,))
                existing_docs = c.fetchall()
            
            conn.close()
            return render_template('existing.html', user_id=user_id, user_name=user_name, existing_docs=existing_docs, codes=codes if url and doc_name else None)
                
        elif 'delete_doc_id' in request.form:
            doc_id = request.form['delete_doc_id']
            user_id = request.form['user_id']
            user_name = request.form['user_name']
            user_id_hash = hash_user_id(user_id)
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            c.execute("DELETE FROM documents WHERE id = ? AND user_id_hash = ?", (doc_id, user_id_hash))
            conn.commit()
            
            c.execute("SELECT id, doc_name, url FROM documents WHERE user_id_hash = ?", (user_id_hash,))
            existing_docs = c.fetchall()
            
            conn.close()
            return render_template('existing.html', user_id=user_id, user_name=user_name, existing_docs=existing_docs)
    
    return render_template('existing.html')

# Forget User ID route
@app.route('/forget', methods=['GET', 'POST'])
def forget():
    if request.method == 'POST':
        if 'forget_code' in request.form:
            forget_code = request.form['forget_code']
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            c.execute("SELECT user_id, user_id_hash, used, created_at FROM forget_codes WHERE code = ?", (forget_code,))
            result = c.fetchone()
            
            if result:
                user_id, user_id_hash, used, created_at = result
                
                created_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                if datetime.now() - created_time >= timedelta(days=7):
                    conn.close()
                    return render_template('forget.html', error="Code has expired.")
                
                if used == 1:
                    conn.close()
                    return render_template('forget.html', error="This code has already been used.")
                
                c.execute("UPDATE forget_codes SET used = 1 WHERE code = ?", (forget_code,))
                conn.commit()
                conn.close()
                
                return render_template('forget.html', retrieved_user_id=user_id)
            
            conn.close()
            return render_template('forget.html', error="Invalid code.")
                
        elif 'user_id' in request.form:
            user_id = request.form['user_id']
            user_id_hash = hash_user_id(user_id)
            
            if not check_user_id_exists(user_id_hash):
                return render_template('forget.html', error="User ID does not exist.")
            
            forget_codes = [generate_code(6) for _ in range(10)]
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            c.execute("DELETE FROM forget_codes WHERE user_id_hash = ?", (user_id_hash,))
            
            for code in forget_codes:
                c.execute("INSERT INTO forget_codes (user_id_hash, user_id, code) VALUES (?, ?, ?)",
                         (user_id_hash, user_id, code))
            
            conn.commit()
            conn.close()
            
            return render_template('forget.html', forget_codes=forget_codes, user_id=user_id)
    
    return render_template('forget.html')

# Route to download codes as TXT
@app.route('/download_codes', methods=['POST'])
def download_codes():
    codes = request.form.getlist('codes[]')
    user_name = request.form['user_name']
    user_id = request.form['user_id']
    url = request.form.get('url', '')
    doc_name = request.form.get('doc_name', '')
    
    content = f"User: {user_name}\nUser ID: {user_id}\n"
    if url and doc_name:
        content += f"Document Name: {doc_name}\nDocument URL: {url}\n"
    
    content += "\nDownload Codes (Valid for 7 days, 1 use each):\n" + "\n".join(codes)
    
    return Response(content, mimetype="text/plain", headers={"Content-Disposition": f"attachment;filename={user_id}_codes.txt"})

# Route to download forget codes as TXT
@app.route('/download_forget_codes', methods=['POST'])
def download_forget_codes():
    codes = request.form.getlist('forget_codes[]')
    user_id = request.form['user_id']
    
    content = f"User ID: {user_id}\n\nForget ID Recovery Codes (Valid for 7 days, 1 use each):\n" + "\n".join(codes)
    
    return Response(content, mimetype="text/plain", headers={"Content-Disposition": f"attachment;filename={user_id}_forget_codes.txt"})

# Download route
@app.route('/download', methods=['GET', 'POST'])
def download():
    if request.method == 'POST':
        code = request.form['code']
        cleanup_db()
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        c.execute("SELECT url, doc_name, user_name, user_id, used, created_at FROM documents WHERE code = ?", (code,))
        result = c.fetchone()
        
        if result:
            url, doc_name, user_name, user_id, used, created_at = result
            
            created_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            if datetime.now() - created_time >= timedelta(days=7):
                conn.close()
                return jsonify({'error': 'Code has expired.'}), 400
            
            if used == 1:
                conn.close()
                return jsonify({'error': 'This code has already been used.'}), 400
            
            c.execute("UPDATE documents SET used = 1 WHERE code = ?", (code,))
            conn.commit()
            conn.close()
            
            return jsonify({'url': url, 'doc_name': doc_name, 'user_name': user_name, 'user_id': user_id})
        
        conn.close()
        return jsonify({'error': 'Invalid code.'}), 400
    
    return render_template('download.html')

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
