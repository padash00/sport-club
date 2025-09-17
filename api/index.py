# api/index.py — верх: конфиг и инициализация
import os
from functools import wraps
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.header import Header

from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# ── Пути к папкам проекта ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT_DIR, 'templates'),
    static_folder=os.path.join(ROOT_DIR, 'static')
)

def env(key, default=None):
    return os.environ.get(key, default)

# ── Секреты/сессии ────────────────────────────────────────────────────────────
app.secret_key = env('SECRET_KEY') or os.urandom(32)

# ── Basic Auth для /admin* ────────────────────────────────────────────────────
ADMIN_USER = env('ADMIN_USER', 'admin')
ADMIN_PASS = env('ADMIN_PASS')  # ОБЯЗАТЕЛЬНО задайте на проде

def _need_auth():
    return Response("Требуется авторизация", 401,
                    {"WWW-Authenticate": 'Basic realm="Admin"'})

def requires_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        ok = auth and (auth.username == ADMIN_USER) and ADMIN_PASS and (auth.password == ADMIN_PASS)
        return fn(*args, **kwargs) if ok else _need_auth()
    return wrapper

# ── База данных: внешний Postgres (DATABASE_URL) или локальный SQLite ─────────
db_url = env('DATABASE_URL')
if db_url:
    # Vercel/Heroku могут отдавать префикс postgres:// → исправим
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
else:
    db_url = 'sqlite:///' + os.path.join(ROOT_DIR, 'sportclub.db')  # локальная разработка

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ── SMTP (все пароли — из ENV) ────────────────────────────────────────────────
app.config['SMTP_SERVER']   = env('SMTP_SERVER', 'smtp.gmail.com')
app.config['SMTP_PORT']     = int(env('SMTP_PORT', '587'))
app.config['SMTP_USERNAME'] = env('SMTP_USERNAME', '')
app.config['SMTP_PASSWORD'] = env('SMTP_PASSWORD', '')
app.config['EMAIL_TO']      = env('EMAIL_TO', '')

# ── Загрузка файлов: локалка vs. Cloudinary (Vercel: использовать внешний стораж) ─
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

UPLOAD_COACHES = os.path.join(app.static_folder, 'images', 'coaches')
UPLOAD_NEWS    = os.path.join(app.static_folder, 'images', 'news')
for p in (UPLOAD_COACHES, UPLOAD_NEWS):
    os.makedirs(p, exist_ok=True)  # локалка; на Vercel это эфемерно

app.config['UPLOAD_FOLDER']       = UPLOAD_COACHES
app.config['UPLOAD_FOLDER_NEWS']  = UPLOAD_NEWS

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Опционально: Cloudinary для продакшена (CLOUDINARY_URL в ENV)
CLOUDINARY_URL = env('CLOUDINARY_URL')
if CLOUDINARY_URL:
    try:
        import cloudinary, cloudinary.uploader
        cloudinary.config(cloudinary_url=CLOUDINARY_URL)
        app.config['USE_CLOUDINARY'] = True
    except Exception as e:
        print("Cloudinary init error:", e)
        app.config['USE_CLOUDINARY'] = False
else:
    app.config['USE_CLOUDINARY'] = False

def save_image(file_storage, subfolder='uploads'):
    """
    Возвращает URL изображения.
    - Если настроен Cloudinary → публичный HTTPS-URL.
    - Иначе сохраняет в /static/<subfolder>/ (только для локальной разработки).
    """
    if not file_storage or file_storage.filename == '' or not allowed_file(file_storage.filename):
        return None

    if app.config.get('USE_CLOUDINARY'):
        res = cloudinary.uploader.upload(file_storage, folder=f"vershina/{subfolder}")
        return res.get('secure_url')

    fname = secure_filename(file_storage.filename)
    local_dir = os.path.join(app.static_folder, subfolder)
    os.makedirs(local_dir, exist_ok=True)
    path = os.path.join(local_dir, fname)
    file_storage.save(path)
    return url_for('static', filename=f"{subfolder}/{fname}", _external=False)

# ── Создаём таблицы идемпотентно ───────────────────────────────────────────────
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print("DB init skipped:", e)

# ── Базовые security-заголовки ────────────────────────────────────────────────
@app.after_request
def add_security_headers(resp):
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    resp.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
    return resp
