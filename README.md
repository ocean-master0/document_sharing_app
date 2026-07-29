<div align="center">

# 📄 DocuShare — Secure Document Sharing

> **One-time download codes. Zero leaks.**  
> Upload a document URL → Get 5 unique codes → Share securely.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=fff)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-000?logo=flask&logoColor=fff)](https://flask.palletsprojects.com)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?logo=supabase&logoColor=fff)](https://supabase.com)
[![bcrypt](https://img.shields.io/badge/Auth-bcrypt-4B8BBE?logo=keybase&logoColor=fff)](https://github.com/pyca/bcrypt)
[![MIT License](https://img.shields.io/badge/License-MIT-6C5CE7?logo=opensourceinitiative&logoColor=fff)](LICENSE)
[![Security](https://img.shields.io/badge/Security-Audited-00C853?logo=shield&logoColor=fff)](document_sharing_app_security_audit.md)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-2ECC40?logo=checkmarx&logoColor=fff)]()

</div>

---

## ✨ Features

| Icon | Feature | What it does |
|:----:|---------|-------------|
| 📤 | **Upload & Share** | Submit a document URL, get 5 unique one-time download codes |
| 🔐 | **Secure by Design** | Each code expires after **7 days** or first use — never reused |
| 📊 | **Dashboard** | Manage documents, generate new codes, track usage, delete |
| 🔑 | **Recovery** | 10-character recovery codes if you forget your user ID |
| 🛡️ | **Session Auth** | Log in once, no repeated password prompts |
| 🧱 | **CSRF Protection** | All forms protected against cross-site request forgery |
| ⏱️ | **Rate Limiting** | Prevents brute-force attacks on auth and code endpoints |
| 🔒 | **Account Lockout** | 5 failed attempts → temporary block |
| ✅ | **URL Validation** | Blocks `javascript:`, `localhost`, private IPs |

---

## 🧰 Tech Stack

<div align="center">

| 🏗️ Layer | 🛠️ Technology |
|:---------|:--------------|
| **Framework** | ![Flask](https://img.shields.io/badge/Flask-3.0.3-000?style=flat-square) |
| **Database** | ![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=flat-square) (PostgreSQL) |
| **Auth** | ![bcrypt](https://img.shields.io/badge/bcrypt-4B8BBE?style=flat-square) + Flask sessions |
| **Security** | ![Talisman](https://img.shields.io/badge/Flask--Talisman-CSP%2FHSTS-8B5CF6?style=flat-square) · ![WTF](https://img.shields.io/badge/Flask--WTF-CSRF-6366F1?style=flat-square) · ![Limiter](https://img.shields.io/badge/Flask--Limiter-EC4899?style=flat-square) |
| **Deployment** | ![Gunicorn](https://img.shields.io/badge/Gunicorn-499848?style=flat-square) |

</div>

---

## 📁 Project Structure

```
📦 document_sharing_app/
├── 🐍 app.py                  # Main Flask application
├── 🗄️ schema.sql              # Supabase/PostgreSQL schema + migrations
├── 📋 requirements.txt        # Python dependencies
├── 🔒 .env                    # Environment variables (credentials)
├── 📖 README.md               # This file
├── 📄 LICENSE                 # MIT License
├── 📝 document_sharing_app_security_audit.md  # Full security audit
├── 🎨 static/
│   ├── 🎭 style.css           # Application styles
│   └── ⚡ script.js           # Client-side JavaScript
└── 📂 templates/
    ├── 🏠 base.html           # Layout template (nav, fonts, icons)
    ├── 📤 index.html          # Upload page + registration receipt
    ├── 🔑 existing.html       # Login form + user dashboard
    ├── 🔍 forget.html         # Recover user ID + recovery codes
    └── ⬇️ download.html       # Code redemption page
```

---

## 🔄 How It Works

### 👤 For Document Owners

```
1️⃣  Register      →  Go to /, enter document URL, name & password
2️⃣  Get Codes     →  App generates 5 unique one-time download codes
3️⃣  Share         →  Send any code to your intended recipient
4️⃣  Manage        →  Log in at /existing to view docs, generate codes, delete
5️⃣  Recover       →  Used /forget to retrieve your user ID
```

### 📥 For Recipients

```
1️⃣  Go to /download
2️⃣  Enter the code you received
3️⃣  ✅ Valid → Document URL is revealed
4️⃣  ❌ Code marked used — cannot be reused
```

---

## 🚀 Setup Guide

### 📋 Prerequisites

- ![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)
- ![Supabase](https://img.shields.io/badge/Supabase%20Account-Free%20Tier-3ECF8E?style=flat-square) — [Sign up](https://supabase.com)

### 📦 1. Clone & Install

```bash
git clone https://github.com/ocean-master0/document_sharing_app.git
cd document_sharing_app
pip install -r requirements.txt
```

### ☁️ 2. Create a Supabase Project

| ⚙️ Setting | 🔍 Where to find it |
|:-----------|:--------------------|
| `SUPABASE_URL` | **Project Settings → API → Project URL** |
| `SUPABASE_ANON_KEY` | **Project Settings → API → anon public key** |

### 🔐 3. Configure Environment

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=use your-anon-public-key-here
SECRET_KEY=your-64-character-hex-secret-key

# Optional:
# ENVIRONMENT=production
# REDIS_URL=redis://your-redis-host:6379
```

> 💡 **Generate a secure key:** `python -c "import secrets; print(secrets.token_hex(32))"`

### 🗄️ 4. Initialize the Database

| Step | Action |
|:----:|:-------|
| 1 | Open **Supabase Dashboard → SQL Editor** |
| 2 | Copy contents of `schema.sql` |
| 3 | Paste & click **Run** |

Creates all tables, indexes, and permissions. ✅

### ▶️ 5. Run the Application

```bash
python app.py
```

Opens at `http://0.0.0.0:5000` 🚀

### 🌐 6. Production Deployment

```bash
gunicorn \
  --workers 4 \
  --worker-class gthread \
  --threads 2 \
  --bind 0.0.0.0:$PORT \
  --timeout 30 \
  --max-requests 1000 \
  app:app
```

Set `ENVIRONMENT=production` to enable:
- ![HTTPS](https://img.shields.io/badge/HTTPS-Forced-2ECC40?style=flat-square)
- ![HSTS](https://img.shields.io/badge/HSTS-Enabled-3498DB?style=flat-square)
- ![Cookies](https://img.shields.io/badge/Secure%20Cookies-Enabled-F1C40F?style=flat-square)

---

## 🔌 API Endpoints

| 🛣️ Method | 🛤️ Route | 📝 Description | 🔑 Auth |
|:----------:|:---------|:---------------|:-------:|
| `GET/POST` | `/` | Register + upload document | ❌ |
| `GET/POST` | `/existing` | Login / Dashboard | ✅ |
| `POST` | `/login` | Login endpoint | ❌ |
| `GET` | `/logout` | Logout | ✅ |
| `GET/POST` | `/forget` | Recover user ID | ❌ |
| `GET/POST` | `/download` | Redeem download code | ❌* |
| `POST` | `/download_codes` | Download codes as .txt | ✅ |
| `POST` | `/download_forget_codes` | Download recovery codes as .txt | ✅ |
| `GET` | `/.well-known/security.txt` | Security disclosure | ❌ |

> *CSRF exempt — codes are single-use by nature.

---

## 🛡️ Security Features

| 🏆 Feature | ⚙️ Implementation | 🎯 Status |
|:-----------|:-----------------|:---------:|
| Password storage | bcrypt with salt (12 rounds) | 🟢 |
| Download codes | SHA-256 hashed before DB storage | 🟢 |
| Recovery codes | SHA-256 hashed before DB storage | 🟢 |
| Sessions | Signed cookies with 8-hour expiry | 🟢 |
| CSRF | Flask-WTF `CSRFProtect` on all POST requests | 🟢 |
| Rate limiting | Per-IP, 10 req/min auth, 20 req/min download | 🟢 |
| Account lockout | 5 failed attempts → temporary block | 🟢 |
| URL validation | Only http/https, blocks private/internal IPs | 🟢 |
| Security headers | CSP, HSTS, XSS Protection, Referrer Policy | 🟢 |
| Timing attacks | Constant-time compare + dummy bcrypt | 🟢 |
| Log injection | CRLF sanitized in log messages | 🟢 |

<details>
<summary>📋 Click to view the full security audit</summary>

A comprehensive security audit identified **19 vulnerabilities** (2 critical, 6 high, 5 medium, 4 low, 2 info) — **all have been fixed**.

See [`document_sharing_app_security_audit.md`](document_sharing_app_security_audit.md) for the complete report.

</details>

---

## 🗄️ Database Schema

### 👤 `users`

| 📌 Column | 🏷️ Type | 📝 Description |
|:----------|:---------|:---------------|
| `user_id_hash` | `TEXT (PK)` | SHA-256 of user ID |
| `password_hash` | `TEXT` | bcrypt hashed password |
| `created_at` | `TIMESTAMPTZ` | Registration timestamp |

### 📄 `documents`

| 📌 Column | 🏷️ Type | 📝 Description |
|:----------|:---------|:---------------|
| `id` | `BIGSERIAL (PK)` | Auto-incrementing ID |
| `url` | `TEXT` | Document URL |
| `doc_name` | `TEXT` | Document name |
| `user_name` | `TEXT` | Owner's display name |
| `user_id_hash` | `TEXT (FK)` | Owner's user ID hash |
| `user_id` | `TEXT` | Owner's user ID (display) |
| `code` | `TEXT (UNIQUE)` | SHA-256 hashed download code |
| `used` | `BOOLEAN` | Whether code has been used |
| `created_at` | `TIMESTAMPTZ` | Creation timestamp |

### 🔑 `forget_codes`

| 📌 Column | 🏷️ Type | 📝 Description |
|:----------|:---------|:---------------|
| `id` | `BIGSERIAL (PK)` | Auto-incrementing ID |
| `user_id_hash` | `TEXT (FK)` | Owner's user ID hash |
| `user_id` | `TEXT` | Owner's user ID |
| `code` | `TEXT (UNIQUE)` | SHA-256 hashed recovery code |
| `used` | `BOOLEAN` | Whether code has been used |
| `created_at` | `TIMESTAMPTZ` | Creation timestamp |

---

## 📜 License

<div align="center">

**MIT** — Copyright © 2026 ocean-master0

See [LICENSE](LICENSE) for full text.

[![Open Source](https://img.shields.io/badge/Open%20Source-❤️-FF6B6B?style=for-the-badge&logo=opensourceinitiative&logoColor=fff)](LICENSE)

</div>
