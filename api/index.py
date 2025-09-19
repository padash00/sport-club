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
from flask import request, redirect, url_for
# ── Пути проекта ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT_DIR, 'templates'),
    static_folder=os.path.join(ROOT_DIR, 'static'),
)

def env(key, default=None): return os.environ.get(key, default)

# ── Флаг serverless (Vercel) ───────────────────────────────────────────────────
IS_SERVERLESS = bool(env('VERCEL') or env('NOW_REGION') or env('AWS_LAMBDA_FUNCTION_NAME'))

# ── Секреты/сессии ────────────────────────────────────────────────────────────
app.secret_key = env('SECRET_KEY') or os.urandom(32)

# ── Basic Auth для /admin* ────────────────────────────────────────────────────
ADMIN_USER = env('ADMIN_USER', 'admin')
ADMIN_PASS = env('ADMIN_PASS')  # ОБЯЗАТЕЛЬНО задать в проде

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

# ── База данных ────────────────────────────────────────────────────────────────
db_url = env('DATABASE_URL')
if db_url and db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
if not db_url:
    db_url = 'sqlite:///' + os.path.join(ROOT_DIR, 'sportclub.db')  # локалка

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ── SMTP ───────────────────────────────────────────────────────────────────────
app.config['SMTP_SERVER']   = env('SMTP_SERVER', 'smtp.gmail.com')
app.config['SMTP_PORT']     = int(env('SMTP_PORT', '587'))
app.config['SMTP_USERNAME'] = env('SMTP_USERNAME', '')
app.config['SMTP_PASSWORD'] = env('SMTP_PASSWORD', '')
app.config['EMAIL_TO']      = env('EMAIL_TO', '')

# ── Загрузки: Cloudinary в проде; локально — в static/ ─────────────────────────
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# относительные подпапки внутри /static
COACHES_SUB = 'images/coaches'
NEWS_SUB    = 'images/news'

UPLOAD_COACHES = os.path.join(app.static_folder, COACHES_SUB)
UPLOAD_NEWS    = os.path.join(app.static_folder, NEWS_SUB)

app.config['UPLOAD_FOLDER'] = UPLOAD_COACHES
app.config['UPLOAD_FOLDER_NEWS'] = UPLOAD_NEWS

# На Vercel (read-only) каталоги не создаём.
if not IS_SERVERLESS:
    os.makedirs(UPLOAD_COACHES, exist_ok=True)
    os.makedirs(UPLOAD_NEWS,    exist_ok=True)
else:
    print("Serverless detected: skip creating static/ directories; uploads require external storage.")

# Cloudinary (если задан CLOUDINARY_URL)
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

def allowed_file(fname:str) -> bool:
    return '.' in fname and fname.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file_storage, subfolder='uploads'):
    """
    Возвращает URL изображения:
      • при настроенном Cloudinary — HTTPS-URL из облака;
      • локально — путь в /static/<subfolder>/;
      • на Vercel без Cloudinary — None (загрузки отключены).
    """
    if not file_storage or file_storage.filename == '' or not allowed_file(file_storage.filename):
        return None

    # Облако в проде
    if app.config.get('USE_CLOUDINARY'):
        try:
            res = cloudinary.uploader.upload(file_storage, folder=f"vershina/{subfolder}")
            return res.get('secure_url')
        except Exception as e:
            print("Cloudinary upload error:", e)
            return None

    # На Vercel без облака — не сохраняем (read-only FS)
    if IS_SERVERLESS:
        print("Uploads disabled on serverless without CLOUDINARY_URL.")
        return None

    # Локальная разработка: сохраняем в static/
    fname = secure_filename(file_storage.filename)
    local_dir = os.path.join(app.static_folder, subfolder)
    os.makedirs(local_dir, exist_ok=True)
    try:
        file_storage.save(os.path.join(local_dir, fname))
        return url_for('static', filename=f"{subfolder}/{fname}", _external=False)
    except OSError as e:
        print(f"Local save failed: {e}")
        return None

# ── Создание таблиц (идемпотентно) ─────────────────────────────────────────────
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print("DB init skipped:", e)

# ── Security-заголовки ─────────────────────────────────────────────────────────
@app.after_request
def add_security_headers(resp):
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    resp.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
    return resp

# --- sanity routes (низ файла) ---

@app.get("/health")
def health():
    return "ok", 200

@app.route("/")
def index():
    return render_template("index.html", title="Главная", latest_news=[])

@app.route("/ski-resort.html", endpoint="ski_resort")
def ski_resort():
    return render_template(
        "ski-resort.html",
        title="Горнолыжная база",
        coaches=[], services=[]
    )

@app.route("/gym.html", endpoint="gym")
def gym():
    return render_template(
        "gym.html",
        title="Тренажерный и батутный зал",
        coaches=[], services=[]
    )

@app.route("/news")
def news_list_all():
    return render_template("news_list_all.html", title="Все новости и акции", articles=[])

@app.route("/contacts.html")
def contacts_page():
    return render_template("contacts.html", title="Контакты")

@app.route("/thank-you.html")
def thank_you():
    return "Спасибо!"

@app.post("/submit")
def submit_form():  # для модального окна записи в ski/gym
    name = request.form.get("userName")
    phone = request.form.get("userPhone")
    print(f"[FORM] Заявка: {name=} {phone=}")
    return redirect(url_for("thank_you"))

@app.post("/submit-contact")
def submit_contact_form():  # форма на /contacts.html
    name = request.form.get('contact_name')
    email_from_user = request.form.get('contact_email')
    subject_from_user = request.form.get('contact_subject', 'Без темы')
    message_text = request.form.get('contact_message')

    # Если SMTP-переменные заданы — пробуем отправить письмо
    try:
        smtp_server = app.config.get('SMTP_SERVER')
        smtp_port   = app.config.get('SMTP_PORT')
        smtp_user   = app.config.get('SMTP_USERNAME')
        smtp_pass   = app.config.get('SMTP_PASSWORD')
        email_to    = app.config.get('EMAIL_TO')

        if all([smtp_server, smtp_port, smtp_user, smtp_pass, email_to]):
            import smtplib
            from email.mime.text import MIMEText
            from email.header import Header

            body = f"""
            <html><body>
                <h2>Сообщение с сайта</h2>
                <p><b>От:</b> {name} ({email_from_user})</p>
                <p><b>Тема:</b> {subject_from_user}</p>
                <hr>
                <pre style="white-space:pre-wrap;">{message_text}</pre>
            </body></html>
            """
            msg = MIMEText(body, 'html', 'utf-8')
            msg['From'] = smtp_user
            msg['To'] = email_to
            msg['Subject'] = Header(f"Сообщение с сайта: {subject_from_user}", 'utf-8')
            if email_from_user:
                msg.add_header('Reply-To', email_from_user)

            server = smtplib.SMTP(smtp_server, int(smtp_port))
            server.ehlo(); server.starttls(); server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, email_to, msg.as_string())
            server.quit()
            print("[CONTACT] письмо отправлено")
        else:
            print("[CONTACT] SMTP не настроен — пропускаем отправку")
    except Exception as e:
        print(f"[CONTACT] ошибка отправки письма: {e}")

    return redirect(url_for("thank_you"))

