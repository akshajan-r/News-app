from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    theme = db.Column(db.String(10), nullable=True)
    embedding_vector = db.Column(db.PickleType, nullable=True)
    unlocked_themes = db.Column(db.String, default='light,dark')  # Comma-separated list of unlocked themes
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    dashboard_layout = db.Column(db.Text, nullable=True)  # Store JSON string of layout
    longest_streak = db.Column(db.Integer, default=0)
    preferred_reading_mode = db.Column(db.String(20), default='original')  # 'original' or 'reader'
    is_admin = db.Column(db.Boolean, default=False)

    # Define relationships with cascade
    article_views = db.relationship('ArticleView', backref=db.backref('user_account'), cascade='all, delete-orphan')
    read_articles = db.relationship('ReadArticle', backref='user_account', cascade='all, delete-orphan')
    search_history = db.relationship('SearchHistory', backref='user_account', cascade='all, delete-orphan')
    bookmarks = db.relationship('Bookmark', backref='user_account', cascade='all, delete-orphan')

    def verify_password(self, password):
        """Verify the user's password"""
        return check_password_hash(self.password_hash, password)

    def set_password(self, password):
        """Set the user's password"""
        self.password_hash = generate_password_hash(password)

class ReadArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    article_title = db.Column(db.String(500), nullable=True)
    article_url = db.Column(db.String(500), nullable=False)
    read_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category = db.Column(db.String(50), nullable=True)
    interaction_strength = db.Column(db.Float, nullable=True)
    bookmarked = db.Column(db.Boolean, default=False)
    source = db.Column(db.String(100), nullable=True)

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    query = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category = db.Column(db.String(50), nullable=True)

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    article_url = db.Column(db.String(500), nullable=False)
    article_title = db.Column(db.String(200))
    bookmarked_at = db.Column(db.DateTime, default=datetime.utcnow)

class ArticleView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    article_url = db.Column(db.String(500), nullable=False)
    article_title = db.Column(db.String(500))
    category = db.Column(db.String(50))
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

class NewsSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    api_key = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    credibility_score = db.Column(db.Float, default=0.0)  # 0-1 score
    added_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_fetched = db.Column(db.DateTime, nullable=True)
    category = db.Column(db.String(50), nullable=True)
    # Define one-to-many relationship with ManagedArticle
    articles = db.relationship('ManagedArticle', backref='news_source', lazy=True)

class ManagedArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(500), nullable=False, unique=True)
    source_id = db.Column(db.Integer, db.ForeignKey('news_source.id'))
    category = db.Column(db.String(50))
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    is_featured = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)

class GlobalSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    universal_theme = db.Column(db.String(50), nullable=True)
    set_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    set_at = db.Column(db.DateTime, default=datetime.utcnow)
