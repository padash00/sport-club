# api/models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    youtube_id = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
