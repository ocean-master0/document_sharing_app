import os
import secrets
import hashlib
import logging
import functools
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
from supabase import create_client, Client
import bcrypt

load_dotenv()

app = Flask(__name__)

secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set! "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
app.secret_key = secret_key
app.permanent_session_lifetime = timedelta(hours=8)

csrf = CSRFProtect(app)

IS_PRODUCTION = os.environ.get('ENVIRONMENT', 'development') == 'production'

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_ANON_KEY')
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY/SUPABASE_ANON_KEY must be set!")

_client = None

def get_supabase():
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

REDIS_URL = os.environ.get("REDIS_URL")
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=REDIS_URL or "memory://",
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
    force_https=IS_PRODUCTION,
    strict_transport_security=IS_PRODUCTION,
    strict_transport_security_max_age=31536000,
    session_cookie_secure=IS_PRODUCTION,
    session_cookie_http_only=True,
    frame_options='DENY',
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 8
FORGET_CODE_LENGTH = 10
MAX_FIELD_LENGTH = 500
PASSWORD_MIN_LENGTH = 8
USER_ID_DIGITS = 10

ALLOWED_SCHEMES = {'http', 'https'}
BLOCKED_HOSTS = {'localhost', '127.0.0.1', '0.0.0.0', '::1'}
BLOCKED_PREFIXES = ('192.168.', '10.', '172.16.', '172.17.', '172.18.', '172.19.',
                    '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.',
                    '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.',
                    '169.254.')

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
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False

def valid_password(password):
    return len(password) >= PASSWORD_MIN_LENGTH

def valid_field(value):
    return len(value) <= MAX_FIELD_LENGTH

def truncate_field(value):
    return value[:MAX_FIELD_LENGTH]

def validate_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False
        hostname = parsed.hostname or ''
        if hostname in BLOCKED_HOSTS or hostname.startswith(BLOCKED_PREFIXES):
            return False
        return bool(parsed.netloc)
    except Exception:
        return False

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
        safe_error = str(e)[:200].replace('\n', ' ').replace('\r', ' ')
        logger.error(f"cleanup failed: {safe_error}")

def user_exists(user_id_hash):
    result = get_supabase().table('users').select('user_id_hash', count='exact').eq('user_id_hash', user_id_hash).execute()
    return result.count is not None and result.count > 0

def authenticate_user(user_id_hash, password):
    result = get_supabase().table('users').select('password_hash').eq('user_id_hash', user_id_hash).execute()
    if result.data:
        return check_password(password, result.data[0]['password_hash'])
    bcrypt.checkpw(b"dummy", b"$2b$12$dummy.hash.to.prevent.timing.attacks.xxxxxx")
    return False

_lockout_attempts = {}

def check_lockout(user_id_hash):
    attempts = _lockout_attempts.get(f"lockout:{user_id_hash}", 0)
    return attempts >= 5

def record_failed_attempt(user_id_hash):
    key = f"lockout:{user_id_hash}"
    _lockout_attempts[key] = _lockout_attempts.get(key, 0) + 1

def clear_attempts(user_id_hash):
    _lockout_attempts.pop(f"lockout:{user_id_hash}", None)

def delete_user(user_id_hash):
    try:
        get_supabase().table('documents').delete().eq('user_id_hash', user_id_hash).execute()
        get_supabase().table('forget_codes').delete().eq('user_id_hash', user_id_hash).execute()
        get_supabase().table('users').delete().eq('user_id_hash', user_id_hash).execute()
        logger.info(f"Deleted user {user_id_hash[:12]}...")
        return True
    except Exception as e:
        safe_error = str(e)[:200].replace('\n', ' ').replace('\r', ' ')
        logger.error(f"delete_user failed: {safe_error}")
        return False

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id_hash' not in session:
            return render_template('existing.html', error="Please log in first.")
        return f(*args, **kwargs)
    return decorated

def safe_filename(user_id, suffix):
    safe = re.sub(r'[^\w\-]', '', user_id)[:30]
    return f"{safe}_{suffix}.txt"

def fetch_dashboard_data(user_id_hash):
    docs = get_supabase().table('documents').select('id,doc_name,url').eq('user_id_hash', user_id_hash).execute()
    user_row = get_supabase().table('documents').select('user_name').eq('user_id_hash', user_id_hash).limit(1).execute()
    user_name = user_row.data[0]['user_name'] if user_row.data else 'User'
    return deduplicate_docs(docs.data), user_name

@app.after_request
def add_security_headers(response):
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

GENERIC_AUTH_ERROR = "Invalid user ID or password."

@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    user_id = request.form.get('user_id', '').strip()[:20]
    password = request.form.get('password', '').strip()
    user_id_hash = hash_user_id(user_id)

    if not user_id or not password:
        return render_template('existing.html', error=GENERIC_AUTH_ERROR)
    if check_lockout(user_id_hash):
        return render_template('existing.html',
            error="Account temporarily locked due to too many failed attempts. Try again later.")
    if not authenticate_user(user_id_hash, password):
        record_failed_attempt(user_id_hash)
        return render_template('existing.html', error=GENERIC_AUTH_ERROR)

    clear_attempts(user_id_hash)
    session.permanent = True
    session['user_id_hash'] = user_id_hash
    session['user_id'] = user_id

    return redirect(url_for('existing'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

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
        if not validate_url(url):
            return render_template('index.html', error="Invalid URL. Only http:// and https:// URLs to public domains are allowed.")

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
            err_str = str(e).lower()
            if 'unique' in err_str or 'duplicate' in err_str:
                return render_template('index.html', error="User ID already exists.")
            safe_error = str(e)[:200].replace('\n', ' ').replace('\r', ' ')
            logger.error(f"Upload failed: {safe_error}")
            return render_template('index.html', error="An error occurred. Please try again.")

        logger.info(f"New user {user_id_hash[:12]}... created")
        session.permanent = True
        session['user_id_hash'] = user_id_hash
        session['user_id'] = user_id
        return render_template('index.html', codes=codes, forget_codes=forget_codes,
                               url=url, doc_name=doc_name, user_name=user_name, user_id=user_id)

    return render_template('index.html')

@app.route('/existing', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def existing():
    if 'user_id_hash' not in session:
        if request.method == 'POST':
            return login()
        return render_template('existing.html')

    user_id_hash = session['user_id_hash']
    user_id = session.get('user_id', '')

    if request.method == 'POST':
        if 'delete_user' in request.form:
            if delete_user(user_id_hash):
                session.clear()
                return render_template('existing.html', success_message="Account deleted successfully.")
            return render_template('existing.html', error="An error occurred.")

        if 'delete_doc_id' in request.form:
            doc_id = request.form.get('delete_doc_id')
            get_supabase().table('documents').delete().eq('id', doc_id).eq('user_id_hash', user_id_hash).execute()
            logger.info(f"Deleted doc {doc_id} for user {user_id_hash[:12]}...")
            existing_docs, user_name = fetch_dashboard_data(user_id_hash)
            return render_template('existing.html', user_id=user_id, user_name=user_name,
                                   existing_docs=existing_docs)

        if 'generate_codes' in request.form:
            gen_url = request.form.get('gen_url', '').strip()
            gen_doc_name = request.form.get('gen_doc_name', '').strip()
            new_codes = [generate_code(CODE_LENGTH) for _ in range(5)] if gen_url and gen_doc_name else None
            if new_codes:
                for code in new_codes:
                    get_supabase().table('documents').insert({
                        'url': gen_url, 'doc_name': gen_doc_name, 'user_name': 'User',
                        'user_id_hash': user_id_hash, 'user_id': user_id, 'code': hash_code(code)
                    }).execute()
            existing_docs, user_name = fetch_dashboard_data(user_id_hash)
            return render_template('existing.html', user_id=user_id, user_name=user_name,
                                   existing_docs=existing_docs, codes=new_codes,
                                   show_codes_for=gen_doc_name)

        user_name = truncate_field(request.form.get('user_name', '').strip())
        url = truncate_field(request.form.get('url', '').strip())
        doc_name = truncate_field(request.form.get('doc_name', '').strip())

        if not user_name:
            _, user_name = fetch_dashboard_data(user_id_hash)

        if not url or not doc_name:
            existing_docs, user_name = fetch_dashboard_data(user_id_hash)
            return render_template('existing.html', user_id=user_id, user_name=user_name,
                                   existing_docs=existing_docs)

        if not validate_url(url):
            existing_docs, user_name = fetch_dashboard_data(user_id_hash)
            return render_template('existing.html', user_id=user_id, user_name=user_name,
                                   existing_docs=existing_docs, error="Invalid URL.")

        new_codes = [generate_code(CODE_LENGTH) for _ in range(5)]
        for code in new_codes:
            get_supabase().table('documents').insert({
                'url': url, 'doc_name': doc_name, 'user_name': user_name,
                'user_id_hash': user_id_hash, 'user_id': user_id, 'code': hash_code(code)
            }).execute()
        existing_docs, _ = fetch_dashboard_data(user_id_hash)
        return render_template('existing.html', user_id=user_id, user_name=user_name,
                               existing_docs=existing_docs, codes=new_codes)

    existing_docs, user_name = fetch_dashboard_data(user_id_hash)
    return render_template('existing.html', user_id=user_id, user_name=user_name,
                           existing_docs=existing_docs)

@app.route('/forget', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
@limiter.limit("10 per hour")
def forget():
    if request.method == 'POST':
        if 'forget_code' in request.form:
            code = request.form.get('forget_code', '').strip()[:20]
            result = get_supabase().table('forget_codes').select('id,used,created_at,user_id').eq('code', hash_code(code)).execute()
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
        if check_lockout(user_id_hash):
            return render_template('forget.html',
                error="Account temporarily locked. Try again later.")
        if not user_exists(user_id_hash):
            return render_template('forget.html', error=GENERIC_AUTH_ERROR)
        if not authenticate_user(user_id_hash, password):
            record_failed_attempt(user_id_hash)
            return render_template('forget.html', error=GENERIC_AUTH_ERROR)

        clear_attempts(user_id_hash)
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
@csrf.exempt
def download():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()[:20]
        cleanup_db()

        result = get_supabase().table('documents').select('id,url,doc_name,user_name,used,created_at').eq('code', hash_code(code)).execute()
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
@limiter.limit("5 per minute")
@login_required
def download_codes():
    user_id = session.get('user_id', '')
    user_name = request.form.get('user_name', '')
    url = request.form.get('url', '')
    doc_name = request.form.get('doc_name', '')
    codes = request.form.getlist('codes[]')

    content = f"User: {user_name}\nUser ID: {user_id}\n"
    if url and doc_name:
        content += f"Document Name: {doc_name}\nDocument URL: {url}\n"
    content += f"\nDownload Codes (Valid for 7 days, 1 use each):\n" + "\n".join(codes)

    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename(user_id, "codes")}"'}
    )

@app.route('/download_forget_codes', methods=['POST'])
@limiter.limit("5 per minute")
@login_required
def download_forget_codes():
    user_id = session.get('user_id', '')
    codes = request.form.getlist('forget_codes[]')

    content = f"User ID: {user_id}\n\nForget ID Recovery Codes (Valid for 7 days, 1 use each):\n" + "\n".join(codes)

    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename(user_id, "forget_codes")}"'}
    )

@app.route('/.well-known/security.txt')
def security_txt():
    return Response(
        "Contact: mailto:security@yourdomain.com\n"
        "Expires: 2027-12-31T23:59:59Z\n",
        mimetype='text/plain'
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
