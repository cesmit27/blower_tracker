# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)  # Primary key for User
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    sightings = db.relationship('Sighting', backref='user', lazy=True)
    timezone = db.Column(db.String(100), default='UTC')

class Sighting(db.Model):
    __tablename__ = 'sightings'
    id = db.Column(db.Integer, primary_key=True)  # Primary key for Sighting
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    datetime = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)
    blower_user = db.Column(db.String(50), nullable=False)
    blower_type = db.Column(db.String(50), nullable=False)
    num_blowers = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(50), nullable=False)
    weather = db.Column(db.String(50), nullable=True)
    noise_level = db.Column(db.Integer, nullable=False)
    anger_level = db.Column(db.Integer, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(50), nullable=False)