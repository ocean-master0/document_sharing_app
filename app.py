import os
import secrets
import hashlib
import logging
import hmac
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from supabase import create_client, Client
import bcrypt

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://placeholder-project.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.placeholder')

_client = None

def get_supabase():
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

talisman = Talisman(app,
    content_security_policy={
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        'style-src': ["'self'", 'https://fonts.googleapis.com', 'https://cdn.jsdelivr.net'],
        'font-src': ['https://fonts.gstatic.com', 'https://cdn.jsdelivr.net'],
        'connect-src': ["'self'"],
    },
    content_security_policy_nonce_in=['script-src'],
    force_https=False,
    strict_transport_security=True,
    session_cookie_secure=False,
    frame_options='DENY',
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 8
FORGET_CODE_LENGTH = 6
MAX_FIELD_LENGTH = 500
PASSWORD_MIN_LENGTH = 8
USER_ID_DIGITS = 10

def now_utc():
    return datetime.now(timezone.utc)

def generate_code(length=CODE_LENGTH):
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(length))

def generate_user_id():
    return ''.join(secrets.choice('0123456789') for _ in range(USER_ID_DIGITS))

def hash_user_id(user_id):
    return hashlib.sha256(user_id.encode()).hexdigest()

def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, password_hash):
    return hmac.compare_digest(bcrypt.hashpw(password.encode(), password_hash.encode()), password_hash.encode())

def valid_password(password):
    return len(password) >= PASSWORD_MIN_LENGTH

def valid_field(value):
    return len(value) <= MAX_FIELD_LENGTH

def truncate_field(value):
    return value[:MAX_FIELD_LENGTH]

def deduplicate_docs(docs_data):
    seen = set()
    result = []
    for doc in docs_data:
        key = (doc['url'], doc['doc_name'])
        if key not in seen:
            seen.add(key)
            result.append(doc)
    return result

def cleanup_db():
    cutoff = (now_utc() - timedelta(days=7)).isoformat()
    try:
        get_supabase().table('documents').delete().lt('created_at', cutoff).execute()
        get_supabase().table('forget_codes').delete().lt('created_at', cutoff).execute()
    except Exception as e:
        logger.error(f"cleanup failed: {e}")

def user_exists(user_id_hash):
    result = get_supabase().table('users').select('user_id_hash', count='exact').eq('user_id_hash', user_id_hash).execute()
    return result.count is not None and result.count > 0

def delete_user(user_id_hash):
    try:
        get_supabase().table('documents').delete().eq('user_id_hash', user_id_hash).execute()
        get_supabase().table('forget_codes').delete().eq('user_id_hash', user_id_hash).execute()
        get_supabase().table('users').delete().eq('user_id_hash', user_id_hash).execute()
        logger.info(f"Deleted user {user_id_hash[:12]}...")
        return True
    except Exception as e:
        logger.error(f"delete_user failed: {e}")
        return False

@app.after_request
def add_security_headers(response):
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

GENERIC_AUTH_ERROR = "Invalid user ID or password."

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def index():
    if request.method == 'POST':
        url = truncate_field(request.form.get('url', '').strip())
        doc_name = truncate_field(request.form.get('doc_name', '').strip())
        user_name = truncate_field(request.form.get('user_name', '').strip())
        custom_user_id = request.form.get('custom_user_id', '').strip()[:20]
        use_custom = request.form.get('use_custom') == 'on'
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        missing = [f for f, v in [('URL', url), ('Document name', doc_name), ('Name', user_name), ('Password', password), ('Confirm password', confirm_password)] if not v]
        if missing:
            return render_template('index.html', error="All fields are required.")

        if not valid_password(password):
            return render_template('index.html', error=f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
        if password != confirm_password:
            return render_template('index.html', error="Passwords do not match.")
        if not valid_field(url) or not valid_field(doc_name) or not valid_field(user_name):
            return render_template('index.html', error="Input too long.")

        user_id = custom_user_id if use_custom and custom_user_id else generate_user_id()
        user_id_hash = hash_user_id(user_id)

        if use_custom and user_exists(user_id_hash):
            return render_template('index.html', error="User ID already exists.")

        codes = [generate_code(CODE_LENGTH) for _ in range(5)]
        forget_codes = [generate_code(FORGET_CODE_LENGTH) for _ in range(10)] if not user_exists(user_id_hash) else None
        password_hash = hash_password(password)

        try:
            get_supabase().table('users').insert({'user_id_hash': user_id_hash, 'password_hash': password_hash}).execute()
            for code in codes:
                get_supabase().table('documents').insert({
                    'url': url, 'doc_name': doc_name, 'user_name': user_name,
                    'user_id_hash': user_id_hash, 'user_id': user_id, 'code': hash_code(code)
                }).execute()
            if forget_codes:
                for code in forget_codes:
                    get_supabase().table('forget_codes').insert({
                        'user_id_hash': user_id_hash, 'user_id': user_id, 'code': hash_code(code)
                    }).execute()
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return render_template('index.html', error="An error occurred. Please try again.")

        logger.info(f"New user {user_id_hash[:12]}... created")
        return render_template('index.html', codes=codes, forget_codes=forget_codes,
                               url=url, doc_name=doc_name, user_name=user_name, user_id=user_id)

    return render_template('index.html')

@app.route('/existing', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def existing():
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        user_id = request.form.get('user_id', '').strip()[:20]
        user_name = truncate_field(request.form.get('user_name', '').strip())
        user_id_hash = hash_user_id(user_id)

        def verify_user():
            result = get_supabase().table('users').select('password_hash').eq('user_id_hash', user_id_hash).execute()
            if result.data:
                return check_password(password, result.data[0]['password_hash'])
            return False

        if not user_id or not password:
            return render_template('existing.html', error=GENERIC_AUTH_ERROR)
        if not user_exists(user_id_hash):
            return render_template('existing.html', error=GENERIC_AUTH_ERROR)

        if 'delete_user' in request.form:
            if not verify_user():
                return render_template('existing.html', error=GENERIC_AUTH_ERROR)
            if delete_user(user_id_hash):
                return render_template('existing.html', success_message="Account deleted successfully.")
            return render_template('existing.html', error="An error occurred.")

        if 'delete_doc_id' in request.form:
            doc_id = request.form.get('delete_doc_id')
            if not verify_user():
                return render_template('existing.html', error=GENERIC_AUTH_ERROR)
            get_supabase().table('documents').delete().eq('id', doc_id).eq('user_id_hash', user_id_hash).execute()
            logger.info(f"Deleted doc {doc_id} for user {user_id_hash[:12]}...")
            docs = get_supabase().table('documents').select('id,doc_name,url').eq('user_id_hash', user_id_hash).execute()
            return render_template('existing.html', user_id=user_id, user_name=user_name,
                                   existing_docs=deduplicate_docs(docs.data))

        if not user_name:
            return render_template('existing.html', error="Name is required.")

        user_row = get_supabase().table('users').select('password_hash').eq('user_id_hash', user_id_hash).execute()
        if not user_row.data:
            get_supabase().table('users').insert({'user_id_hash': user_id_hash, 'password_hash': hash_password(password)}).execute()
            logger.info(f"Legacy user {user_id_hash[:12]}... created password")
        elif not check_password(password, user_row.data[0]['password_hash']):
            return render_template('existing.html', error=GENERIC_AUTH_ERROR)

        if 'generate_codes' in request.form:
            if not verify_user():
                return render_template('existing.html', error=GENERIC_AUTH_ERROR)
            gen_url = request.form.get('gen_url', '').strip()
            gen_doc_name = request.form.get('gen_doc_name', '').strip()
            new_codes = [generate_code(CODE_LENGTH) for _ in range(5)] if gen_url and gen_doc_name else None
            if new_codes:
                for code in new_codes:
                    get_supabase().table('documents').insert({
                        'url': gen_url, 'doc_name': gen_doc_name, 'user_name': user_name,
                        'user_id_hash': user_id_hash, 'user_id': user_id, 'code': hash_code(code)
                    }).execute()
            docs = get_supabase().table('documents').select('id,doc_name,url').eq('user_id_hash', user_id_hash).execute()
            return render_template('existing.html', user_id=user_id, user_name=user_name,
                                   existing_docs=deduplicate_docs(docs.data), codes=new_codes,
                                   show_codes_for=gen_doc_name)

        docs = get_supabase().table('documents').select('id,doc_name,url').eq('user_id_hash', user_id_hash).execute()
        existing_docs = deduplicate_docs(docs.data)

        url = truncate_field(request.form.get('url', '').strip())
        doc_name = truncate_field(request.form.get('doc_name', '').strip())
        new_codes = None
        if url and doc_name:
            new_codes = [generate_code(CODE_LENGTH) for _ in range(5)]
            for code in new_codes:
                get_supabase().table('documents').insert({
                    'url': url, 'doc_name': doc_name, 'user_name': user_name,
                    'user_id_hash': user_id_hash, 'user_id': user_id, 'code': hash_code(code)
                }).execute()
            docs = get_supabase().table('documents').select('id,doc_name,url').eq('user_id_hash', user_id_hash).execute()
            existing_docs = deduplicate_docs(docs.data)

        return render_template('existing.html', user_id=user_id, user_name=user_name,
                               existing_docs=existing_docs, codes=new_codes)

    return render_template('existing.html')

@app.route('/forget', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def forget():
    if request.method == 'POST':
        if 'forget_code' in request.form:
            code = request.form.get('forget_code', '').strip()[:20]
            result = get_supabase().table('forget_codes').select('*').eq('code', hash_code(code)).execute()
            row = result.data[0] if result.data else None

            if not row:
                return render_template('forget.html', error="Invalid recovery code.")
            if row['used']:
                return render_template('forget.html', error="This code has already been used.")

            created = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
            if now_utc() - created >= timedelta(days=7):
                return render_template('forget.html', error="Code has expired.")

            get_supabase().table('forget_codes').update({'used': True}).eq('id', row['id']).execute()
            return render_template('forget.html', retrieved_user_id=row['user_id'])

        user_id = request.form.get('user_id', '').strip()[:20]
        password = request.form.get('password', '').strip()
        user_id_hash = hash_user_id(user_id)

        if not user_id or not password:
            return render_template('forget.html', error=GENERIC_AUTH_ERROR)
        if not user_exists(user_id_hash):
            return render_template('forget.html', error=GENERIC_AUTH_ERROR)

        user_row = get_supabase().table('users').select('password_hash').eq('user_id_hash', user_id_hash).execute()
        if not user_row.data or not check_password(password, user_row.data[0]['password_hash']):
            return render_template('forget.html', error=GENERIC_AUTH_ERROR)

        forget_codes = [generate_code(FORGET_CODE_LENGTH) for _ in range(10)]
        get_supabase().table('forget_codes').delete().eq('user_id_hash', user_id_hash).execute()
        for fc in forget_codes:
            get_supabase().table('forget_codes').insert({
                'user_id_hash': user_id_hash, 'user_id': user_id, 'code': hash_code(fc)
            }).execute()

        logger.info(f"Generated new recovery codes for {user_id_hash[:12]}...")
        return render_template('forget.html', forget_codes=forget_codes, user_id=user_id)

    return render_template('forget.html')

@app.route('/download', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def download():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()[:20]
        cleanup_db()

        result = get_supabase().table('documents').select('*').eq('code', hash_code(code)).execute()
        row = result.data[0] if result.data else None

        if not row:
            return jsonify({'error': 'Invalid code.'}), 400

        if row['used']:
            return jsonify({'error': 'This code has already been used.'}), 400

        created = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
        if now_utc() - created >= timedelta(days=7):
            return jsonify({'error': 'Code has expired.'}), 400

        get_supabase().table('documents').update({'used': True}).eq('id', row['id']).execute()
        logger.info(f"Code used for document {row['id']}")

        return jsonify({'url': row['url'], 'doc_name': row['doc_name'], 'user_name': row['user_name']})

    return render_template('download.html')

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
    content += f"\nDownload Codes (Valid for 7 days, 1 use each):\n" + "\n".join(codes)

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
