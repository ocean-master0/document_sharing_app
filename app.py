import secrets
from flask import Flask, render_template, request, jsonify, Response
import sqlite3
import hashlib
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

DB_PATH = 'database.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    try:
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
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (user_id_hash TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_documents_user_hash ON documents(user_id_hash)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_documents_code ON documents(code)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_forget_codes_code ON forget_codes(code)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_forget_codes_user_hash ON forget_codes(user_id_hash)''')
        conn.commit()
    finally:
        conn.close()

def cleanup_db():
    conn = get_db()
    try:
        c = conn.cursor()
        expiration_time = datetime.now() - timedelta(days=7)
        c.execute("DELETE FROM documents WHERE created_at < ?", (expiration_time,))
        c.execute("DELETE FROM forget_codes WHERE created_at < ?", (expiration_time,))
        conn.commit()
    finally:
        conn.close()

def hash_user_id(user_id):
    return hashlib.sha256(user_id.encode()).hexdigest()

def generate_user_id():
    return ''.join(secrets.choice('0123456789') for _ in range(10))

def generate_code(length=4):
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def check_user_id_exists(user_id_hash):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM documents WHERE user_id_hash = ?", (user_id_hash,))
        return c.fetchone()[0] > 0
    finally:
        conn.close()

def delete_user(user_id_hash):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM documents WHERE user_id_hash = ?", (user_id_hash,))
        c.execute("DELETE FROM forget_codes WHERE user_id_hash = ?", (user_id_hash,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False
    finally:
        conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        doc_name = request.form.get('doc_name', '').strip()
        user_name = request.form.get('user_name', '').strip()
        custom_user_id = request.form.get('custom_user_id', '').strip()
        use_custom = request.form.get('use_custom') == 'on'
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not url or not doc_name or not user_name or not password or not confirm_password:
            return render_template('index.html', error="All fields are required.")

        if len(password) < 6:
            return render_template('index.html', error="Password must be at least 6 characters.")

        if password != confirm_password:
            return render_template('index.html', error="Passwords do not match.")

        cleanup_db()

        user_id = custom_user_id if use_custom and custom_user_id else generate_user_id()
        user_id_hash = hash_user_id(user_id)
        password_hash = hash_user_id(password)

        if use_custom and check_user_id_exists(user_id_hash):
            return render_template('index.html', error="User ID already exists.")

        codes = [generate_code(4) for _ in range(5)]
        forget_codes = [generate_code(6) for _ in range(10)] if not check_user_id_exists(user_id_hash) else None
        result_forget = forget_codes

        conn = get_db()
        try:
            c = conn.cursor()
            for code in codes:
                c.execute("INSERT INTO documents (url, doc_name, user_name, user_id_hash, user_id, code) VALUES (?, ?, ?, ?, ?, ?)",
                         (url, doc_name, user_name, user_id_hash, user_id, code))
            if forget_codes:
                for code in forget_codes:
                    c.execute("INSERT INTO forget_codes (user_id_hash, user_id, code) VALUES (?, ?, ?)",
                             (user_id_hash, user_id, code))
            c.execute("INSERT OR IGNORE INTO users (user_id_hash, password_hash) VALUES (?, ?)",
                     (user_id_hash, password_hash))
            conn.commit()
        finally:
            conn.close()

        return render_template('index.html', codes=codes, forget_codes=result_forget,
                               url=url, doc_name=doc_name, user_name=user_name, user_id=user_id)

    return render_template('index.html')

@app.route('/existing', methods=['GET', 'POST'])
def existing():
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        user_id = request.form.get('user_id', '').strip()
        user_name = request.form.get('user_name', '').strip()
        user_id_hash = hash_user_id(user_id)
        password_hash = hash_user_id(password)

        def verify_password():
            conn = get_db()
            try:
                c = conn.cursor()
                c.execute("SELECT password_hash FROM users WHERE user_id_hash = ?", (user_id_hash,))
                row = c.fetchone()
                if row:
                    return row['password_hash'] == password_hash
                return False
            finally:
                conn.close()

        if 'delete_user' in request.form:
            if not user_id or not password:
                return render_template('existing.html', error="User ID and password are required.")
            if not verify_password():
                return render_template('existing.html', error="Invalid password.")
            if delete_user(user_id_hash):
                return render_template('existing.html', success_message="Your account has been successfully deleted.")
            return render_template('existing.html', error="An error occurred while deleting your account.")

        if 'delete_doc_id' in request.form:
            doc_id = request.form.get('delete_doc_id')
            if not user_id or not password:
                return render_template('existing.html', error="User ID and password are required.")
            if not verify_password():
                return render_template('existing.html', error="Invalid password.")

            conn = get_db()
            try:
                c = conn.cursor()
                c.execute("DELETE FROM documents WHERE id = ? AND user_id_hash = ?", (doc_id, user_id_hash))
                conn.commit()
                c.execute("SELECT id, doc_name, url FROM documents WHERE user_id_hash = ?", (user_id_hash,))
                existing_docs = c.fetchall()
                return render_template('existing.html', user_id=user_id, user_name=user_name, existing_docs=existing_docs)
            finally:
                conn.close()

        if not user_id or not user_name or not password:
            return render_template('existing.html', error="User ID, name, and password are required.")

        conn = get_db()
        try:
            c = conn.cursor()
            c.execute("SELECT id, doc_name, url FROM documents WHERE user_id_hash = ?", (user_id_hash,))
            existing_docs = c.fetchall()

            if not existing_docs:
                return render_template('existing.html', error="User ID does not exist.")

            c.execute("SELECT password_hash FROM users WHERE user_id_hash = ?", (user_id_hash,))
            user_row = c.fetchone()
            if not user_row:
                c.execute("INSERT INTO users (user_id_hash, password_hash) VALUES (?, ?)",
                         (user_id_hash, password_hash))
                conn.commit()
            elif user_row['password_hash'] != password_hash:
                return render_template('existing.html', error="Invalid password.")
            else:
                conn.commit()

            url = request.form.get('url', '').strip()
            doc_name = request.form.get('doc_name', '').strip()
            new_codes = None
            if url and doc_name:
                new_codes = [generate_code(4) for _ in range(5)]
                for code in new_codes:
                    c.execute("INSERT INTO documents (url, doc_name, user_name, user_id_hash, user_id, code) VALUES (?, ?, ?, ?, ?, ?)",
                             (url, doc_name, user_name, user_id_hash, user_id, code))
                conn.commit()
                c.execute("SELECT id, doc_name, url FROM documents WHERE user_id_hash = ?", (user_id_hash,))
                existing_docs = c.fetchall()

            return render_template('existing.html', user_id=user_id, user_name=user_name,
                                   existing_docs=existing_docs, codes=new_codes)
        finally:
            conn.close()

    return render_template('existing.html')

@app.route('/forget', methods=['GET', 'POST'])
def forget():
    if request.method == 'POST':
        if 'forget_code' in request.form:
            forget_code = request.form.get('forget_code', '').strip()

            conn = get_db()
            try:
                c = conn.cursor()
                c.execute("UPDATE forget_codes SET used = 1 WHERE code = ? AND used = 0", (forget_code,))
                if c.rowcount == 0:
                    c.execute("SELECT used, created_at FROM forget_codes WHERE code = ?", (forget_code,))
                    result = c.fetchone()
                    if result:
                        created_time = datetime.strptime(result['created_at'], '%Y-%m-%d %H:%M:%S')
                        if datetime.now() - created_time >= timedelta(days=7):
                            return render_template('forget.html', error="Code has expired.")
                        return render_template('forget.html', error="This code has already been used.")
                    return render_template('forget.html', error="Invalid code.")

                c.execute("SELECT user_id FROM forget_codes WHERE code = ?", (forget_code,))
                result = c.fetchone()
                conn.commit()
                return render_template('forget.html', retrieved_user_id=result['user_id'])
            finally:
                conn.close()

        if 'user_id' in request.form:
            user_id = request.form.get('user_id', '').strip()
            password = request.form.get('password', '').strip()
            user_id_hash = hash_user_id(user_id)
            password_hash = hash_user_id(password)

            if not password:
                return render_template('forget.html', error="Password is required.")

            if not check_user_id_exists(user_id_hash):
                return render_template('forget.html', error="User ID does not exist.")

            conn = get_db()
            try:
                c = conn.cursor()
                c.execute("SELECT password_hash FROM users WHERE user_id_hash = ?", (user_id_hash,))
                user_row = c.fetchone()
                if not user_row or user_row['password_hash'] != password_hash:
                    return render_template('forget.html', error="Invalid password.")
            finally:
                conn.close()

            forget_codes = [generate_code(6) for _ in range(10)]

            conn = get_db()
            try:
                c = conn.cursor()
                c.execute("DELETE FROM forget_codes WHERE user_id_hash = ?", (user_id_hash,))
                for code in forget_codes:
                    c.execute("INSERT INTO forget_codes (user_id_hash, user_id, code) VALUES (?, ?, ?)",
                             (user_id_hash, user_id, code))
                conn.commit()
                return render_template('forget.html', forget_codes=forget_codes, user_id=user_id)
            finally:
                conn.close()

    return render_template('forget.html')

@app.route('/download_codes', methods=['POST'])
def download_codes():
    codes = request.form.getlist('codes[]')
    user_name = request.form.get('user_name', '')
    user_id = request.form.get('user_id', '')
    url = request.form.get('url', '')
    doc_name = request.form.get('doc_name', '')
    safe_filename = ''.join(c for c in user_id if c.isalnum() or c in '._-')[:50]

    content = f"User: {user_name}\nUser ID: {user_id}\n"
    if url and doc_name:
        content += f"Document Name: {doc_name}\nDocument URL: {url}\n"
    content += "\nDownload Codes (Valid for 7 days, 1 use each):\n" + "\n".join(codes)

    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment;filename={safe_filename}_codes.txt"}
    )

@app.route('/download_forget_codes', methods=['POST'])
def download_forget_codes():
    codes = request.form.getlist('forget_codes[]')
    user_id = request.form.get('user_id', '')
    safe_filename = ''.join(c for c in user_id if c.isalnum() or c in '._-')[:50]

    content = f"User ID: {user_id}\n\nForget ID Recovery Codes (Valid for 7 days, 1 use each):\n" + "\n".join(codes)

    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment;filename={safe_filename}_forget_codes.txt"}
    )

@app.route('/download', methods=['GET', 'POST'])
def download():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        cleanup_db()

        conn = get_db()
        try:
            c = conn.cursor()
            c.execute("UPDATE documents SET used = 1 WHERE code = ? AND used = 0", (code,))
            if c.rowcount == 0:
                c.execute("SELECT used, created_at FROM documents WHERE code = ?", (code,))
                result = c.fetchone()
                if result:
                    created_time = datetime.strptime(result['created_at'], '%Y-%m-%d %H:%M:%S')
                    if datetime.now() - created_time >= timedelta(days=7):
                        return jsonify({'error': 'Code has expired.'}), 400
                    return jsonify({'error': 'This code has already been used.'}), 400
                return jsonify({'error': 'Invalid code.'}), 400

            c.execute("SELECT url, doc_name, user_name, user_id FROM documents WHERE code = ?", (code,))
            result = c.fetchone()
            conn.commit()
            return jsonify({'url': result['url'], 'doc_name': result['doc_name'], 'user_name': result['user_name']})

            return jsonify({'error': 'Invalid code.'}), 400
        finally:
            conn.close()

    return render_template('download.html')

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
