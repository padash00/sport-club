# api/index.py
import os
from functools import wraps
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
import smtplib
from urllib.parse import quote_plus
from flask import Flask, render_template, request, redirect, url_for, Response
# импорт SQLAlchemy оставлен, хотя экземпляр берём из api.models (не создаём новый!)
from werkzeug.utils import secure_filename

# ЕДИНЫЙ db + модель Course живут в api/models.py
from api.models import db, Course

# ───────────────────────── Папки проекта ─────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT_DIR, 'templates'),
    static_folder=os.path.join(ROOT_DIR, 'static'),
)

def env(key: str, default=None) -> str | None:
    return os.environ.get(key, default)

# ────────────────── Флаги окружения / безопасность ───────────────
IS_SERVERLESS = bool(env('VERCEL') or env('NOW_REGION') or env('AWS_LAMBDA_FUNCTION_NAME'))
app.secret_key = env('SECRET_KEY') or os.urandom(32)

ADMIN_USER = env('ADMIN_USER', 'admin')
ADMIN_PASS = env('ADMIN_PASS')  # установи в Vercel → Project → Settings → Environment Variables

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

# ────────────────────────── База данных ──────────────────────────
db_url = env('DATABASE_URL')
if db_url and db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
if not db_url:
    # ВНИМАНИЕ: на Vercel FS read-only. SQLite годится только локально.
    db_url = 'sqlite:///' + os.path.join(ROOT_DIR, 'sportclub.db')

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}

# ИНИЦИАЛИЗИРУЕМ ЕДИНЫЙ db, НЕ СОЗДАЁМ НОВЫЙ SQLAlchemy(app)!
db.init_app(app)

# ───────────────────── SMTP (контакты на сайте) ──────────────────
app.config['SMTP_SERVER']   = env('SMTP_SERVER', 'smtp.gmail.com')
app.config['SMTP_PORT']     = int(env('SMTP_PORT', '587'))
app.config['SMTP_USERNAME'] = env('SMTP_USERNAME', '')
app.config['SMTP_PASSWORD'] = env('SMTP_PASSWORD', '')
app.config['EMAIL_TO']      = env('EMAIL_TO', '')

# ───────────────────── WhatsApp (запись) ─────────────────────
SITE_WA_PHONE = env('SITE_WA_PHONE', '')  # Пример: +77071234567
SITE_WA_TEXT  = env('SITE_WA_TEXT', 'Здравствуйте! Хочу записаться')

# ───────────────────── Загрузка изображений ──────────────────────
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
COACHES_SUB = "images/coaches"
NEWS_SUB    = "images/news"

def allowed_file(fname: str) -> bool:
    return "." in fname and fname.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

CLOUDINARY_URL = env("CLOUDINARY_URL")
USE_CLOUDINARY = False
if CLOUDINARY_URL:
    try:
        import cloudinary, cloudinary.uploader  # type: ignore
        cloudinary.config(cloudinary_url=CLOUDINARY_URL, secure=True)
        USE_CLOUDINARY = True
        print("Cloudinary enabled.")
    except Exception as e:  # noqa: BLE001
        print("Cloudinary init error:", e)
        USE_CLOUDINARY = False

def store_image(file_storage, rel_subdir: str, cloud_folder: str | None = None):
    """
    Возвращает dict {"url": <путь/https>, "id": <public_id|None>} или None.
    """
    if not file_storage or file_storage.filename == "" or not allowed_file(file_storage.filename):
        return None

    # Прод: Cloudinary
    if USE_CLOUDINARY:
        try:
            folder = f"vershina/{(cloud_folder or rel_subdir).strip('/')}"
            res = cloudinary.uploader.upload(  # type: ignore
                file_storage,
                folder=folder,
                resource_type="image",
                unique_filename=True,
                overwrite=False,
            )
            return {"url": res.get("secure_url"), "id": res.get("public_id")}
        except Exception as e:  # noqa: BLE001
            print("Cloudinary upload error:", e)
            return None

    # Серверлес без облака — сохранить нельзя
    if IS_SERVERLESS:
        print(f"Uploads disabled on serverless without CLOUDINARY_URL (file={file_storage.filename})")
        return None

    # Локально: сохраняем в static/
    fname = secure_filename(file_storage.filename)
    local_dir = os.path.join(app.static_folder, rel_subdir)
    os.makedirs(local_dir, exist_ok=True)
    file_storage.save(os.path.join(local_dir, fname))
    return {"url": f"{rel_subdir}/{fname}", "id": None}

def delete_image(public_id: str | None):
    if USE_CLOUDINARY and public_id:
        try:
            cloudinary.uploader.destroy(public_id, invalidate=True, resource_type="image")  # type: ignore
        except Exception as e:  # noqa: BLE001
            print("Cloudinary delete error:", e)

def media_url(path: str | None) -> str:
    if not path:
        return ""
    return path if path.startswith(("http://", "https://")) else url_for("static", filename=path)

def make_wa_link(phone: str | None, text: str | None = None) -> str:
    """
    Делает корректную ссылку wa.me с предзаполненным текстом.
    phone — международный номер, можно с + и пробелами (+7707...).
    """
    if not phone:
        return "#"
    digits = "".join(ch for ch in phone if ch.isdigit())
    msg = quote_plus(text or "")
    return f"https://wa.me/{digits}?text={msg}"


@app.context_processor
def inject_media_helpers():
    return {
        "media_url": media_url,
        "wa_link": make_wa_link,
        "SITE_WA_PHONE": SITE_WA_PHONE,
        "SITE_WA_TEXT": SITE_WA_TEXT,
    }


# ─────────────────────────── Модели ──────────────────────────────
# Эти модели используют ЕДИНЫЙ db из api.models
class Coach(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    experience = db.Column(db.Text)
    specialization = db.Column(db.String(200))
    photo_path = db.Column(db.String(300))
    section = db.Column(db.String(50), nullable=False)  # 'ski' | 'gym'

    def __repr__(self):
        return f"<Coach {self.name}>"

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    duration = db.Column(db.String(50))
    section = db.Column(db.String(50), nullable=False)  # 'ski' | 'gym'

    def __repr__(self):
        return f"<Service {self.name}>"

class NewsArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    pub_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    image_path = db.Column(db.String(300))

    def __repr__(self):
        return f"<NewsArticle {self.title}>"

with app.app_context():
    try:
        db.create_all()
    except Exception as e:  # noqa: BLE001
        print("DB init skipped/failed:", e)

# ───────────────────── Security заголовки ────────────────────────
@app.after_request
def add_security_headers(resp):
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    resp.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
    return resp

# ─────────────────── Публичные страницы сайта ───────────────────
@app.get("/health")
def health():
    return "ok", 200

@app.route("/")
def index():
    latest_news = NewsArticle.query.order_by(NewsArticle.pub_date.desc()).limit(3).all()
    return render_template("index.html", title="Главная", latest_news=latest_news)

@app.route("/ski-resort.html", endpoint="ski_resort")
def ski_resort():
    coaches = Coach.query.filter_by(section='ski').order_by(Coach.name).all()
    services = Service.query.filter_by(section='ski').order_by(Service.name).all()
    return render_template("ski-resort.html",
                           title="Горнолыжная база",
                           coaches=coaches, services=services)

@app.route("/gym.html", endpoint="gym")
def gym():
    coaches = Coach.query.filter_by(section='gym').order_by(Coach.name).all()
    services = Service.query.filter_by(section='gym').order_by(Service.name).all()
    return render_template("gym.html",
                           title="Тренажерный и батутный зал",
                           coaches=coaches, services=services)

@app.route("/news")
def news_list_all():
    articles = NewsArticle.query.order_by(NewsArticle.pub_date.desc()).all()
    return render_template("news_list_all.html", title="Все новости и акции", articles=articles)

@app.route('/news/<int:article_id>')
def news_article_detail(article_id: int):
    article = NewsArticle.query.get_or_404(article_id)
    return render_template('news_article_detail.html', article=article, title=article.title)

@app.route("/contacts.html")
def contacts_page():
    return render_template("contacts.html", title="Контакты")

@app.route("/thank-you.html")
def thank_you():
    return "Спасибо!"

# ───────────── Видеокурсы (публичная страница) ─────────────
@app.route("/courses")
def courses():
    items = Course.query.order_by(Course.id.desc()).all()
    return render_template("courses.html", title="Видеокурсы", courses=items)

# ───────────── Формы с сайта (нужны шаблонам!) ─────────────
@app.route("/submit", methods=["POST"])
def submit_form():
    name = request.form.get("userName")
    phone = request.form.get("userPhone")
    print(f"[FORM] Заявка: name={name!r} phone={phone!r}")
    return redirect(url_for("thank_you"))

@app.route("/submit-contact", methods=["POST"])
def submit_contact_form():
    name = request.form.get('contact_name')
    email_from_user = request.form.get('contact_email')
    subject_from_user = request.form.get('contact_subject', 'Без темы')
    message_text = request.form.get('contact_message')

    try:
        smtp_server = app.config['SMTP_SERVER']
        smtp_port   = int(app.config['SMTP_PORT'])
        smtp_user   = app.config['SMTP_USERNAME']
        smtp_pass   = app.config['SMTP_PASSWORD']
        email_to    = app.config['EMAIL_TO']

        if all([smtp_server, smtp_port, smtp_user, smtp_pass, email_to]):
            body = f"""
            <html><body>
                <h2>Сообщение с сайта СК "Алтайские Барсы"</h2>
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

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.ehlo(); server.starttls(); server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, email_to, msg.as_string())
            server.quit()
            print("[CONTACT] письмо отправлено")
        else:
            print("[CONTACT] SMTP не настроен — пропускаем отправку")
    except Exception as e:  # noqa: BLE001
        print(f"[CONTACT] ошибка отправки письма: {e}")

    return redirect(url_for("thank_you"))

# ───────────────────────── Админ-панель ──────────────────────────
@app.route("/admin")
@requires_admin
def admin_root():
    return redirect(url_for("admin_coaches_list"))

# --- Курсы (админка) ---
@app.route("/admin/courses")
@requires_admin
def admin_courses_list():
    items = Course.query.order_by(Course.id.desc()).all()
    return render_template("admin/admin_courses_list.html",
                           title="Управление курсами", courses=items)

@app.route("/admin/courses/add", methods=["GET", "POST"])
@requires_admin
def admin_add_course():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        youtube_id = request.form.get("youtube_id", "").strip()
        description = request.form.get("description", "").strip()

        if not title or not youtube_id:
            return render_template("admin/admin_course_form.html",
                                   title="Ошибка: заполните обязательные поля",
                                   form_action=url_for("admin_add_course"),
                                   error="Название и YouTube ID обязательны.")

        db.session.add(Course(title=title, youtube_id=youtube_id, description=description))
        db.session.commit()
        return redirect(url_for("admin_courses_list"))

    return render_template("admin/admin_course_form.html",
                           title="Добавить курс",
                           form_action=url_for("admin_add_course"))

@app.route("/admin/courses/edit/<int:course_id>", methods=["GET", "POST"])
@requires_admin
def admin_edit_course(course_id):
    course = Course.query.get_or_404(course_id)

    if request.method == "POST":
        course.title = request.form.get("title", "").strip()
        course.youtube_id = request.form.get("youtube_id", "").strip()
        course.description = request.form.get("description", "").strip()

        if not course.title or not course.youtube_id:
            return render_template("admin/admin_course_form.html",
                                   title="Ошибка: заполните обязательные поля",
                                   course=course,
                                   form_action=url_for("admin_edit_course", course_id=course.id),
                                   error="Название и YouTube ID обязательны.")
        db.session.commit()
        return redirect(url_for("admin_courses_list"))

    return render_template("admin/admin_course_form.html",
                           title="Редактировать курс",
                           course=course,
                           form_action=url_for("admin_edit_course", course_id=course.id))

@app.route("/admin/courses/delete/<int:course_id>", methods=["POST"])
@requires_admin
def admin_delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    return redirect(url_for("admin_courses_list"))

# --- Тренеры ---
@app.route('/admin/coaches')
@requires_admin
def admin_coaches_list():
    coaches = Coach.query.order_by(Coach.name).all()
    return render_template('admin/admin_coaches_list.html',
                           coaches=coaches, title="Управление тренерами")

@app.route('/admin/coaches/add', methods=['GET', 'POST'])
@requires_admin
def admin_add_coach():
    if request.method == 'POST':
        name = request.form.get('name')
        experience = request.form.get('experience')
        specialization = request.form.get('specialization')
        section = request.form.get('section')

        img = store_image(request.files.get('photo_file'), COACHES_SUB, 'coaches')
        photo_url = img['url'] if img else None

        if not name or not section:
            return render_template('admin/admin_coach_form.html',
                                   title="Ошибка: Заполните поля",
                                   form_action=url_for('admin_add_coach'),
                                   error="Имя и секция обязательны.")

        db.session.add(Coach(
            name=name, experience=experience, specialization=specialization,
            section=section, photo_path=photo_url
        ))
        db.session.commit()
        return redirect(url_for('admin_coaches_list'))

    return render_template('admin/admin_coach_form.html',
                           title="Добавить нового тренера",
                           form_action=url_for('admin_add_coach'))

@app.route('/admin/coaches/edit/<int:coach_id>', methods=['GET', 'POST'])
@requires_admin
def admin_edit_coach(coach_id: int):
    coach = Coach.query.get_or_404(coach_id)
    if request.method == 'POST':
        coach.name = request.form.get('name')
        coach.experience = request.form.get('experience')
        coach.specialization = request.form.get('specialization')
        coach.section = request.form.get('section')

        img = store_image(request.files.get('photo_file'), COACHES_SUB, 'coaches')
        if img:
            coach.photo_path = img['url']

        db.session.commit()
        return redirect(url_for('admin_coaches_list'))

    return render_template('admin/admin_coach_form.html',
                           title="Редактировать тренера",
                           form_action=url_for('admin_edit_coach', coach_id=coach_id),
                           coach=coach)

@app.route('/admin/coaches/delete/<int:coach_id>', methods=['POST'])
@requires_admin
def admin_delete_coach(coach_id: int):
    coach = Coach.query.get_or_404(coach_id)
    db.session.delete(coach)
    db.session.commit()
    return redirect(url_for('admin_coaches_list'))

# --- Услуги ---
@app.route('/admin/services')
@requires_admin
def admin_services_list():
    services_ski = Service.query.filter_by(section='ski').order_by(Service.name).all()
    services_gym = Service.query.filter_by(section='gym').order_by(Service.name).all()
    return render_template('admin/admin_services_list.html',
                           services_ski=services_ski, services_gym=services_gym,
                           title="Управление услугами")

@app.route('/admin/services/add', methods=['GET', 'POST'])
@requires_admin
def admin_add_service():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price_str = request.form.get('price')
        duration = request.form.get('duration')
        section = request.form.get('section')

        if not name or not price_str or not section:
            return render_template('admin/admin_service_form.html',
                                   title="Ошибка: Заполните все обязательные поля",
                                   form_action=url_for('admin_add_service'),
                                   error="Название, цена и секция обязательны.")
        try:
            price = float(price_str)
            if price < 0:
                raise ValueError("Цена не может быть отрицательной")
        except ValueError as e:
            return render_template('admin/admin_service_form.html',
                                   title="Ошибка: Некорректная цена",
                                   form_action=url_for('admin_add_service'),
                                   error=f"Цена должна быть положительным числом. {e}")

        db.session.add(Service(
            name=name, description=description, price=price,
            duration=duration, section=section
        ))
        db.session.commit()
        return redirect(url_for('admin_services_list'))

    return render_template('admin/admin_service_form.html',
                           title="Добавить новую услугу",
                           form_action=url_for('admin_add_service'))

@app.route('/admin/services/edit/<int:service_id>', methods=['GET', 'POST'])
@requires_admin
def admin_edit_service(service_id: int):
    service = Service.query.get_or_404(service_id)
    if request.method == 'POST':
        service.name = request.form.get('name')
        service.description = request.form.get('description')
        price_str = request.form.get('price')
        service.duration = request.form.get('duration')
        service.section = request.form.get('section')

        if not service.name or not price_str or not service.section:
            return render_template('admin/admin_service_form.html',
                                   title="Ошибка: Заполните все обязательные поля",
                                   form_action=url_for('admin_edit_service', service_id=service_id),
                                   service=service,
                                   error="Название, цена и секция обязательны.")
        try:
            service.price = float(price_str)
            if service.price < 0:
                raise ValueError("Цена не может быть отрицательной")
        except ValueError as e:
            return render_template('admin/admin_service_form.html',
                                   title="Ошибка: Некорректная цена",
                                   form_action=url_for('admin_edit_service', service_id=service_id),
                                   service=service,
                                   error=f"Цена должна быть положительным числом. {e}")

        db.session.commit()
        return redirect(url_for('admin_services_list'))

    return render_template('admin/admin_service_form.html',
                           title="Редактировать услугу",
                           form_action=url_for('admin_edit_service', service_id=service_id),
                           service=service)

@app.route('/admin/services/delete/<int:service_id>', methods=['POST'])
@requires_admin
def admin_delete_service(service_id: int):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    return redirect(url_for('admin_services_list'))

# --- Новости ---
@app.route('/admin/news')
@requires_admin
def admin_news_list():
    news = NewsArticle.query.order_by(NewsArticle.pub_date.desc()).all()
    return render_template('admin/admin_news_list.html',
                           articles=news, title="Управление новостями")

@app.route('/admin/news/add', methods=['GET', 'POST'])
@requires_admin
def admin_add_news():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if not title or not content:
            return render_template('admin/admin_news_form.html',
                                   title="Ошибка: Заполните заголовок и текст",
                                   form_action=url_for('admin_add_news'),
                                   error="Заголовок и текст новости обязательны.")

        img = store_image(request.files.get('image_file'), NEWS_SUB, 'news')
        img_url = img['url'] if img else None

        db.session.add(NewsArticle(title=title, content=content, image_path=img_url))
        db.session.commit()
        return redirect(url_for('admin_news_list'))

    return render_template('admin/admin_news_form.html',
                           title="Добавить новость",
                           form_action=url_for('admin_add_news'))

@app.route('/admin/news/edit/<int:article_id>', methods=['GET', 'POST'])
@requires_admin
def admin_edit_news(article_id: int):
    article = NewsArticle.query.get_or_404(article_id)
    if request.method == 'POST':
        article.title = request.form.get('title')
        article.content = request.form.get('content')

        img = store_image(request.files.get('image_file'), NEWS_SUB, 'news')
        if img:
            article.image_path = img['url']

        if not article.title or not article.content:
            return render_template('admin/admin_news_form.html',
                                   title="Ошибка: Заполните заголовок и текст",
                                   form_action=url_for('admin_edit_news', article_id=article_id),
                                   article=article,
                                   error="Заголовок и текст новости обязательны.")
        db.session.commit()
        return redirect(url_for('admin_news_list'))

    return render_template('admin/admin_news_form.html',
                           title="Редактировать новость",
                           form_action=url_for('admin_edit_news', article_id=article_id),
                           article=article)

@app.route('/admin/news/delete/<int:article_id>', methods=['POST'])
@requires_admin
def admin_delete_news(article_id: int):
    article = NewsArticle.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    return redirect(url_for('admin_news_list'))

# ─────────────────────────── Локальный запуск ───────────────────
if __name__ == "__main__":
    app.run(debug=True)




