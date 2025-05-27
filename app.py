import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.header import Header

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sportclub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = os.path.join(app.static_folder, 'images', 'coaches')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SMTP_SERVER'] = 'smtp.gmail.com' 
app.config['SMTP_PORT'] = 587 
app.config['SMTP_USERNAME'] = 'padash00@gmail.com' 
app.config['SMTP_PASSWORD'] = 'Papamama98' 
app.config['EMAIL_TO'] = 'padash00@gmail.com'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

UPLOAD_FOLDER_NEWS = os.path.join(app.static_folder, 'images', 'news')
app.config['UPLOAD_FOLDER_NEWS'] = UPLOAD_FOLDER_NEWS  # Регистрируем новый ключ для новостей

if not os.path.exists(app.config['UPLOAD_FOLDER_NEWS']):
    os.makedirs(app.config['UPLOAD_FOLDER_NEWS'])


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Coach(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    experience = db.Column(db.Text, nullable=True)
    specialization = db.Column(db.String(200), nullable=True)
    photo_path = db.Column(db.String(200), nullable=True)
    section = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Coach {self.name}>'

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    duration = db.Column(db.String(50), nullable=True)
    section = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Service {self.name}>'

class NewsArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)           # Заголовок новости
    content = db.Column(db.Text, nullable=False)                # Полный текст новости
    pub_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Дата публикации (автоматически ставится текущая)
    image_path = db.Column(db.String(200), nullable=True)     # Опционально: путь к картинке для новости

    def __repr__(self):
        return f'<NewsArticle {self.title}>'

# ... (в app.py, внутри определения маршрутов) ...

@app.route('/')
def index():
    # Получаем, например, 3 последние новости, 
    # отсортированные по дате публикации (новые вверху)
    latest_news = NewsArticle.query.order_by(NewsArticle.pub_date.desc()).limit(3).all()
    return render_template('index.html', 
                           title="Главная", 
                           latest_news=latest_news) # Передаем новости в шаблон

@app.route('/ski-resort.html')
def ski_resort():
    ski_coaches = Coach.query.filter_by(section='ski').order_by(Coach.name).all()
    # НОВОЕ: Получаем услуги для секции 'ski', отсортированные по имени
    ski_services = Service.query.filter_by(section='ski').order_by(Service.name).all()
    return render_template('ski-resort.html', 
                           coaches=ski_coaches, 
                           services=ski_services, # Передаем услуги в шаблон
                           title="Горнолыжная база")

@app.route('/gym.html')
def gym():
    gym_coaches = Coach.query.filter_by(section='gym').order_by(Coach.name).all()
    # НОВОЕ: Получаем услуги для секции 'gym', отсортированные по имени
    gym_services = Service.query.filter_by(section='gym').order_by(Service.name).all()
    return render_template('gym.html', 
                           coaches=gym_coaches, 
                           services=gym_services, # Передаем услуги в шаблон
                           title="Тренажерный и батутный зал")

@app.route('/thank-you.html')
def thank_you():
    return render_template('thank-you.html', title="Спасибо!")

@app.route('/submit', methods=['POST'])
def submit_form():
    if request.method == 'POST':
        name = request.form['userName']
        phone = request.form['userPhone']
        print(f'ПОЛУЧЕНА ЗАЯВКА (старая форма): Имя - {name}, Телефон - {phone}')
        return redirect(url_for('thank_you'))
    return redirect(url_for('index'))

@app.route('/admin/coaches')
def admin_coaches_list():
    coaches = Coach.query.order_by(Coach.name).all()
    return render_template('admin/admin_coaches_list.html', coaches=coaches, title="Управление тренерами")

@app.route('/admin/coaches/add', methods=['GET', 'POST'])
def admin_add_coach():
    if request.method == 'POST':
        name = request.form.get('name')
        experience = request.form.get('experience')
        specialization = request.form.get('specialization')
        section = request.form.get('section')
        photo_path_to_save = None

        if 'photo_file' in request.files:
            file = request.files['photo_file']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_path_to_save = f"images/coaches/{filename}"
        
        if not name or not section:
            return render_template('admin/admin_coach_form.html', title="Ошибка: Заполните поля", form_action=url_for('admin_add_coach'), error="Имя и секция обязательны.")

        new_coach = Coach(name=name, experience=experience, specialization=specialization, photo_path=photo_path_to_save, section=section)
        db.session.add(new_coach)
        db.session.commit()
        return redirect(url_for('admin_coaches_list'))
    return render_template('admin/admin_coach_form.html', title="Добавить нового тренера", form_action=url_for('admin_add_coach'))

@app.route('/admin/coaches/edit/<int:coach_id>', methods=['GET', 'POST'])
def admin_edit_coach(coach_id):
    coach_to_edit = Coach.query.get_or_404(coach_id)
    if request.method == 'POST':
        coach_to_edit.name = request.form.get('name')
        coach_to_edit.experience = request.form.get('experience')
        coach_to_edit.specialization = request.form.get('specialization')
        coach_to_edit.section = request.form.get('section')
        
        if 'photo_file' in request.files:
            file = request.files['photo_file']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                if coach_to_edit.photo_path:
                    old_photo_full_path = os.path.join(app.static_folder, coach_to_edit.photo_path)
                    if os.path.exists(old_photo_full_path):
                        try:
                            os.remove(old_photo_full_path)
                        except OSError as e:
                            print(f"Ошибка удаления старого фото: {e}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                coach_to_edit.photo_path = f"images/coaches/{filename}"
        
        db.session.commit()
        return redirect(url_for('admin_coaches_list'))
    return render_template('admin/admin_coach_form.html', title="Редактировать тренера", form_action=url_for('admin_edit_coach', coach_id=coach_id), coach=coach_to_edit)

@app.route('/admin/coaches/delete/<int:coach_id>', methods=['POST'])
def admin_delete_coach(coach_id):
    coach_to_delete = Coach.query.get_or_404(coach_id)
    if coach_to_delete.photo_path:
        photo_full_path = os.path.join(app.static_folder, coach_to_delete.photo_path)
        if os.path.exists(photo_full_path):
            try:
                os.remove(photo_full_path)
            except OSError as e:
                print(f"Ошибка удаления фото при удалении тренера: {e}")
    db.session.delete(coach_to_delete)
    db.session.commit()
    return redirect(url_for('admin_coaches_list'))

@app.route('/admin/services')
def admin_services_list():
    services_ski = Service.query.filter_by(section='ski').order_by(Service.name).all()
    services_gym = Service.query.filter_by(section='gym').order_by(Service.name).all()
    return render_template('admin/admin_services_list.html', services_ski=services_ski, services_gym=services_gym, title="Управление услугами")

@app.route('/admin/services/add', methods=['GET', 'POST'])
def admin_add_service():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price_str = request.form.get('price')
        duration = request.form.get('duration')
        section = request.form.get('section')

        if not name or not price_str or not section:
            return render_template('admin/admin_service_form.html', title="Ошибка: Заполните все обязательные поля", form_action=url_for('admin_add_service'), error="Название, цена и секция обязательны.")
        try:
            price = float(price_str)
            if price < 0: raise ValueError("Цена не может быть отрицательной")
        except ValueError as e:
            return render_template('admin/admin_service_form.html', title="Ошибка: Некорректная цена", form_action=url_for('admin_add_service'), error=f"Цена должна быть положительным числом. {e}")

        new_service = Service(name=name, description=description, price=price, duration=duration, section=section)
        db.session.add(new_service)
        db.session.commit()
        return redirect(url_for('admin_services_list'))
    return render_template('admin/admin_service_form.html', title="Добавить новую услугу", form_action=url_for('admin_add_service'))

@app.route('/admin/services/edit/<int:service_id>', methods=['GET', 'POST'])
def admin_edit_service(service_id):
    service_to_edit = Service.query.get_or_404(service_id)
    if request.method == 'POST':
        service_to_edit.name = request.form.get('name')
        service_to_edit.description = request.form.get('description')
        price_str = request.form.get('price')
        service_to_edit.duration = request.form.get('duration')
        service_to_edit.section = request.form.get('section')

        if not service_to_edit.name or not price_str or not service_to_edit.section:
            return render_template('admin/admin_service_form.html', title="Ошибка: Заполните все обязательные поля", form_action=url_for('admin_edit_service', service_id=service_id), service=service_to_edit, error="Название, цена и секция обязательны.")
        try:
            service_to_edit.price = float(price_str)
            if service_to_edit.price < 0: raise ValueError("Цена не может быть отрицательной")
        except ValueError as e:
            return render_template('admin/admin_service_form.html', title="Ошибка: Некорректная цена", form_action=url_for('admin_edit_service', service_id=service_id), service=service_to_edit, error=f"Цена должна быть положительным числом. {e}")
        
        db.session.commit()
        return redirect(url_for('admin_services_list'))
    return render_template('admin/admin_service_form.html', title="Редактировать услугу", form_action=url_for('admin_edit_service', service_id=service_id), service=service_to_edit)

@app.route('/admin/services/delete/<int:service_id>', methods=['POST'])
def admin_delete_service(service_id):
    service_to_delete = Service.query.get_or_404(service_id)
    db.session.delete(service_to_delete)
    db.session.commit()
    return redirect(url_for('admin_services_list'))

@app.route('/admin/news')
def admin_news_list():
    # Получаем все новости, сортируем по дате публикации (новые вверху)
    news_articles = NewsArticle.query.order_by(NewsArticle.pub_date.desc()).all() 
    return render_template('admin/admin_news_list.html', 
                           articles=news_articles, 
                           title="Управление новостями")

@app.route('/admin/news/add', methods=['GET', 'POST'])
def admin_add_news():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        image_path_to_save = None # Инициализируем путь к картинке

        if 'image_file' in request.files:
            file = request.files['image_file']
            # Проверяем, что файл выбран, имеет имя и разрешенное расширение
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename) # Безопасное имя файла
                # Сохраняем файл в папку static/images/news/
                file.save(os.path.join(app.config['UPLOAD_FOLDER_NEWS'], filename))
                # В базу сохраняем путь относительно папки static/
                image_path_to_save = f"images/news/{filename}" 

        if not title or not content:
            return render_template('admin/admin_news_form.html', 
                                   title="Ошибка: Заполните заголовок и текст",
                                   form_action=url_for('admin_add_news'),
                                   error="Заголовок и текст новости обязательны.")

        new_article = NewsArticle(
            title=title,
            content=content,
            image_path=image_path_to_save # Сохраняем путь или None
            # pub_date установится автоматически
        )
        db.session.add(new_article)
        db.session.commit()
        return redirect(url_for('admin_news_list'))

    return render_template('admin/admin_news_form.html', 
                           title="Добавить новость",
                           form_action=url_for('admin_add_news'))

# ... (после функции admin_add_news) ...

@app.route('/admin/news/edit/<int:article_id>', methods=['GET', 'POST'])
def admin_edit_news(article_id):
    article_to_edit = NewsArticle.query.get_or_404(article_id)

    if request.method == 'POST':
        article_to_edit.title = request.form.get('title')
        article_to_edit.content = request.form.get('content')
        
        # Обработка файла картинки при редактировании
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                # Опционально: удаляем старую картинку, если она была и загружается новая
                if article_to_edit.image_path:
                    old_image_full_path = os.path.join(app.static_folder, article_to_edit.image_path)
                    if os.path.exists(old_image_full_path):
                        try:
                            os.remove(old_image_full_path)
                        except OSError as e:
                            print(f"Ошибка удаления старой картинки новости: {e}")
                
                file.save(os.path.join(app.config['UPLOAD_FOLDER_NEWS'], filename))
                article_to_edit.image_path = f"images/news/{filename}"
            # Если файл не выбран, но есть текстовый путь (на случай если оставили поле image_path)
            # Это можно убрать, если вы полностью перешли на input type="file"
            elif request.form.get('image_path_text_fallback'):
                 article_to_edit.image_path = request.form.get('image_path_text_fallback')


        if not article_to_edit.title or not article_to_edit.content:
            return render_template('admin/admin_news_form.html', 
                                   title="Ошибка: Заполните заголовок и текст", 
                                   form_action=url_for('admin_edit_news', article_id=article_id),
                                   article=article_to_edit,
                                   error="Заголовок и текст новости обязательны.")
        
        db.session.commit()
        return redirect(url_for('admin_news_list'))

    return render_template('admin/admin_news_form.html', 
                           title="Редактировать новость", 
                           form_action=url_for('admin_edit_news', article_id=article_id), 
                           article=article_to_edit)


@app.route('/admin/news/delete/<int:article_id>', methods=['POST'])
def admin_delete_news(article_id):
    article_to_delete = NewsArticle.query.get_or_404(article_id)
    
    # Опционально: удаляем файл картинки, если он был связан с новостью
    if article_to_delete.image_path:
        image_full_path = os.path.join(app.static_folder, article_to_delete.image_path)
        if os.path.exists(image_full_path):
            try:
                os.remove(image_full_path)
            except OSError as e:
                print(f"Ошибка удаления файла картинки новости: {e}")

    db.session.delete(article_to_delete)
    db.session.commit()
    return redirect(url_for('admin_news_list'))

@app.route('/news/<int:article_id>')
def news_article_detail(article_id):
    article = NewsArticle.query.get_or_404(article_id) # Получаем статью по ID или показываем ошибку 404
    return render_template('news_article_detail.html', 
                           article=article, 
                           title=article.title) # Используем заголовок статьи для тега <title>

@app.route('/news')
def news_list_all():
    # Получаем все новости, сортируем по дате публикации (новые вверху)
    all_articles = NewsArticle.query.order_by(NewsArticle.pub_date.desc()).all()
    return render_template('news_list_all.html', 
                           articles=all_articles, 
                           title="Все новости и акции")

@app.route('/contacts.html')
def contacts_page():
    return render_template('contacts.html', title="Контакты")

@app.route('/submit-contact', methods=['POST'])
def submit_contact_form():
    if request.method == 'POST':
        name = request.form.get('contact_name')
        email_from_user = request.form.get('contact_email') # Email пользователя
        subject_from_user = request.form.get('contact_subject', 'Без темы') # Тема от пользователя
        message_text = request.form.get('contact_message')

        if not name or not email_from_user or not message_text:
            # В идеале, вернуть на страницу контактов с сообщением об ошибке
            # Можно использовать flash сообщения Flask: from flask import flash
            # flash('Пожалуйста, заполните все обязательные поля.', 'error')
            # return redirect(url_for('contacts_page'))
            return "Ошибка: Пожалуйста, заполните все обязательные поля и вернитесь назад.", 400


        # Используем SMTP-настройки из app.config
        smtp_server_val = app.config.get('SMTP_SERVER')
        smtp_port_val = app.config.get('SMTP_PORT')
        smtp_username_val = app.config.get('SMTP_USERNAME')
        smtp_password_val = app.config.get('SMTP_PASSWORD')
        email_to_admin = app.config.get('EMAIL_TO')

        if not all([smtp_server_val, smtp_port_val, smtp_username_val, smtp_password_val, email_to_admin]):
            print("ОШИБКА: SMTP конфигурация не полная в app.config!")
            return "Ошибка сервера: не настроена отправка почты.", 500

        email_subject_to_admin = f"Сообщение с сайта СК 'Вершина': {subject_from_user}"
        email_body_to_admin = f"""
        <html><body>
            <h2>Новое сообщение с формы обратной связи:</h2>
            <p><strong>От:</strong> {name} ({email_from_user})</p>
            <p><strong>Тема:</strong> {subject_from_user}</p>
            <hr>
            <p><strong>Сообщение:</strong></p>
            <p style="white-space: pre-wrap;">{message_text}</p>
        </body></html>
        """

        msg = MIMEText(email_body_to_admin, 'html', 'utf-8')
        msg['From'] = smtp_username_val # Письмо отправляется с вашего "серверного" ящика
        msg['To'] = email_to_admin
        msg['Subject'] = Header(email_subject_to_admin, 'utf-8')
        msg.add_header('Reply-To', email_from_user) # Чтобы вы могли ответить прямо пользователю

        try:
            print(f"Попытка отправки письма с формы контактов на {email_to_admin} через {smtp_server_val}...")
            # Если ваш сервер использует SSL (порт 465), используйте:
            # server = smtplib.SMTP_SSL(smtp_server_val, smtp_port_val)
            # Для TLS/STARTTLS (порт 587):
            server = smtplib.SMTP(smtp_server_val, int(smtp_port_val)) # Убедимся, что порт это число
            server.ehlo()
            server.starttls()
            server.ehlo()
            
            server.login(smtp_username_val, smtp_password_val)
            server.sendmail(smtp_username_val, email_to_admin, msg.as_string())
            server.quit()
            print("Письмо с формы контактов успешно отправлено!")
            # Перенаправляем на страницу благодарности
            return redirect(url_for('thank_you')) 
        except Exception as e:
            print(f"Ошибка при отправке письма с формы контактов: {e}")
            # Здесь можно перенаправить на страницу с сообщением об ошибке
            return f"Произошла ошибка при отправке вашего сообщения: {e}", 500

    # Если кто-то пытается зайти на /submit-contact не методом POST
    return redirect(url_for('contacts_page'))
if __name__ == '__main__':
    app.run(debug=True)