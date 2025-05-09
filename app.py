from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, redirect, url_for, request, session, jsonify, flash, send_from_directory, g
import requests
from flask_login import current_user, LoginManager, UserMixin, login_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, HiddenField
from wtforms.validators import DataRequired, Length, EqualTo
from flask_wtf.csrf import CSRFProtect, generate_csrf
from models import db, User, SearchHistory, ReadArticle, Bookmark, ArticleView, NewsSource, ManagedArticle, GlobalSettings
import numpy as np
from recommendation_model import RecommendationModel
from sqlalchemy import func
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk
from textblob import TextBlob
from collections import defaultdict
from enum import Enum
import json
import os
from dotenv import load_dotenv
from flask_migrate import Migrate
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from functools import wraps
import concurrent.futures

# Load environment variables
load_dotenv()

# Get environment variables
FLASK_APP = os.getenv('FLASK_APP')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///newsapp.db')  # Add default SQLite URL
SECRET_KEY = os.getenv('SECRET_KEY', 'dev')  # Add default secret key

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
csrf = CSRFProtect(app)
csrf.init_app(app)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
# Initialize the recommendation model
recommendation_model = RecommendationModel()

COUNTRIES = {
    "US": "United States",
}

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except:
        return None

@app.before_request
def before_request():
    if 'csrf_token' not in session:
        session['csrf_token'] = generate_csrf()

@app.after_request
def after_request(response):
    response.headers.set('X-CSRFToken', session.get('csrf_token', ''))
    return response

@app.route("/get_recommended_articles")
@login_required
def get_recommended_articles():
    try:
        articles = []
        
        # Always get trending/breaking news first
        url = f"https://newsapi.org/v2/top-headlines?apiKey={NEWS_API_KEY}&pageSize=15&language=en"
        response = requests.get(url)
        if response.ok:
            articles_data = response.json().get('articles', [])
            # Add category to each article
            for article in articles_data:
                # Try to determine category from source or section if available
                article['category'] = article.get('category') or \
                                    article.get('source', {}).get('category') or \
                                    'general'  # Default category
            articles.extend(articles_data)
        
        # If user has history, enhance with personalized content
        user_history = ReadArticle.query.filter_by(user_id=current_user.id)\
            .order_by(ReadArticle.read_at.desc())\
            .limit(20).all()
            
        if user_history:
            # Add category-based articles
            categories = db.session.query(
                ReadArticle.category,
                func.count(ReadArticle.category).label('count')
            ).filter(
                ReadArticle.user_id == current_user.id,
                ReadArticle.category.isnot(None)
            ).group_by(ReadArticle.category)\
            .order_by(func.count(ReadArticle.category).desc())\
            .limit(2).all()
            
            for category in categories:
                params = {
                    'apiKey': NEWS_API_KEY,
                    'category': category[0],
                    'pageSize': 5,
                    'language': 'en'
                }
                response = requests.get(url, params=params)
                if response.ok:
                    category_articles = response.json().get('articles', [])
                    # Add category to each article
                    for article in category_articles:
                        article['category'] = category[0]
                    articles.extend(category_articles)
        
        # Process all articles
        articles = merge_recommendations(articles, [])  # Remove duplicates
        articles = extract_topics(articles)
        
        for article in articles:
            score = calculate_article_score(article, user_history if user_history else [])
            article['relevance_score'] = score
            # Ensure category is set
            if 'category' not in article:
                article['category'] = 'general'
        
        articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return jsonify({'articles': articles[:6]})
        
    except Exception as e:
        print(f"Error in recommendations: {e}")
        # Fallback to basic news if anything fails
        url = f"https://newsapi.org/v2/top-headlines?apiKey={NEWS_API_KEY}&pageSize=6&language=en"
        response = requests.get(url)
        if response.ok:
            articles = response.json().get('articles', [])
            # Add default category
            for article in articles:
                article['category'] = 'general'
            return jsonify({'articles': articles})
        return jsonify({'error': str(e)}), 500

def get_similar_users(user_id, limit=5):
    """Find users with similar reading patterns"""
    current_user_categories = db.session.query(
        ReadArticle.category,
        func.count(ReadArticle.category).label('count')
    ).filter(
        ReadArticle.user_id == user_id,
        ReadArticle.category.isnot(None)
    ).group_by(ReadArticle.category).all()
    
    # Get users who read similar categories
    similar_users = db.session.query(
        ReadArticle.user_id,
        func.count(ReadArticle.id).label('overlap')
    ).filter(
        ReadArticle.user_id != user_id,
        ReadArticle.category.in_([c[0] for c in current_user_categories])
    ).group_by(
        ReadArticle.user_id
    ).order_by(
        func.count(ReadArticle.id).desc()
    ).limit(limit).all()
    
    return [u[0] for u in similar_users]

def analyze_sentiment(text):
    """Analyze sentiment of text using TextBlob"""
    try:
        analysis = TextBlob(text)
        # Returns (polarity, subjectivity)
        # polarity: -1 to 1 (negative to positive)
        # subjectivity: 0 to 1 (objective to subjective)
        return analysis.sentiment
    except:
        return (0, 0)

def calculate_article_score(article, user_history):
    """Calculate relevance score with enhanced factors including sentiment"""
    total_score = 0
    
    # 1. Time-based score (0-25 points)
    try:
        pub_date = datetime.strptime(article.get('publishedAt', ''), '%Y-%m-%dT%H:%M:%SZ')
        time_diff = datetime.now(timezone.utc) - pub_date
        hours_old = time_diff.total_seconds() / 3600
        if hours_old <= 24:  # Less than 24 hours old
            total_score += 25
        elif hours_old <= 48:  # Less than 48 hours old
            total_score += 15
        elif hours_old <= 72:  # Less than 72 hours old
            total_score += 10
        else:
            total_score += 5
    except:
        total_score += 5  # Default score if date parsing fails
    
    # 2. Topic matching (0-25 points)
    if article.get('topic'):
        user_topics = set()
        for hist in user_history:
            if hasattr(hist, 'topic') and hist.topic:
                user_topics.update(hist.topic)
        topic_overlap = len(set(article['topic']) & user_topics)
        total_score += min(topic_overlap * 8, 25)  # 8 points per topic match, max 25
    
    # 3. Sentiment analysis (0-25 points)
    title_sentiment = analyze_sentiment(article.get('title', ''))
    desc_sentiment = analyze_sentiment(article.get('description', ''))
    article_sentiment = (title_sentiment[0] + desc_sentiment[0]) / 2
    
    user_sentiment = get_user_sentiment_preference(user_history)
    sentiment_diff = abs(article_sentiment - user_sentiment)
    sentiment_match = max(0, 1 - sentiment_diff)  # 0 to 1 score
    total_score += sentiment_match * 25
    
    # Store sentiment info for display
    article['sentiment'] = {
        'polarity': article_sentiment,
        'label': get_sentiment_label(article_sentiment),
        'match_score': round(sentiment_match * 100)
    }
    
    # 4. Source matching (0-25 points)
    if article.get('source', {}).get('name') in [h.source for h in user_history if hasattr(h, 'source')]:
        total_score += 25
    
    # Normalize to 0-100
    final_score = min(round(total_score), 100)
    
    return final_score

def get_user_sentiment_preference(user_history):
    """Calculate user's preferred sentiment based on reading history"""
    if not user_history:
        return 0  # Neutral default
        
    sentiments = []
    for article in user_history:
        if article.article_title:
            sentiment = analyze_sentiment(article.article_title)[0]
            sentiments.append(sentiment)
    
    return sum(sentiments) / len(sentiments) if sentiments else 0

def get_sentiment_label(polarity):
    """Convert sentiment polarity to human-readable label"""
    if polarity > 0.5:
        return 'Very Positive'
    elif polarity > 0:
        return 'Positive'
    elif polarity == 0:
        return 'Neutral'
    elif polarity > -0.5:
        return 'Negative'
    else:
        return 'Very Negative'

class NewsFilterForm(FlaskForm):
    category = SelectField('Category', choices=[
        ('', 'All Categories'),
        ('business', 'Business'),
        ('entertainment', 'Entertainment'),
        ('health', 'Health'),
        ('science', 'Science'),
        ('sports', 'Sports'),
        ('technology', 'Technology')
    ])
    keywords = StringField('Keywords')
    country = SelectField('Country', choices=[
        ('', 'All Countries'),
        ('us', 'United States')
    ])
    csrf_token = HiddenField()

@app.route("/get_news", methods=['GET', 'POST'])
@login_required
def get_news():
    form = NewsFilterForm()
    # Handle both initial page load and form submissions
    if request.method == 'GET':
        # Show default news on initial page load
        url = f"https://newsapi.org/v2/top-headlines"
        params = {
            'apiKey': NEWS_API_KEY,
            'language': 'en',
            'pageSize': 30
        }
        try:
            response = requests.get(url, params=params)
            if response.ok:
                articles = response.json().get('articles', [])
                return render_template('news.html', 
                                    articles=articles, 
                                    form=form,
                                    show_categories=True)
        except Exception as e:
            print(f"Error fetching initial news: {e}")
            flash('Error fetching news. Please try again.', 'error')
    
    elif request.method == 'POST':
        try:
            # Build the API URL
            url = "https://newsapi.org/v2/top-headlines?"
            params = {
                'apiKey': NEWS_API_KEY,
                'language': 'en',
                'pageSize': 30
            }
            
            # Add optional parameters if provided
            if form.category.data:
                params['category'] = form.category.data
            if form.keywords.data:
                params['q'] = form.keywords.data
            if form.country.data:
                params['country'] = form.country.data
                
            response = requests.get(url, params=params)
            if response.ok:
                articles = response.json().get('articles', [])
                
                # Process articles to ensure image URLs are properly formatted
                for article in articles:
                    if article.get('urlToImage'):
                        if not article['urlToImage'].startswith(('http://', 'https://')):
                            article['urlToImage'] = f"https:{article['urlToImage']}" if article['urlToImage'].startswith('//') else f"https://{article['urlToImage']}"
                    else:
                        article['urlToImage'] = None
                
                return render_template('news.html', 
                                     articles=articles, 
                                     form=form,
                                     show_categories=True)
        except Exception as e:
            print(f"Error fetching news: {e}")
            flash('Error fetching news. Please try again.', 'error')
    
    # Default view with empty results
    return render_template('news.html', 
                         articles=[], 
                         form=form,
                         show_categories=True)

def get_user_stats(user_id):
    # Get most active day
    most_active_day_query = db.session.query(
        func.strftime('%w', ReadArticle.read_at).label('day_of_week'),
        func.count(ReadArticle.id)
    ).filter_by(user_id=user_id).group_by('day_of_week').order_by(func.count(ReadArticle.id).desc()).first()

    day_map = {
        '0': 'Sunday', '1': 'Monday', '2': 'Tuesday', '3': 'Wednesday',
        '4': 'Thursday', '5': 'Friday', '6': 'Saturday'
    }
    most_active_day = day_map.get(most_active_day_query[0], 'N/A') if most_active_day_query else 'N/A'

    # Get peak reading time
    peak_time_query = db.session.query(
        func.strftime('%H', ReadArticle.read_at).label('hour'),
        func.count(ReadArticle.id)
    ).filter_by(user_id=user_id).group_by('hour').order_by(func.count(ReadArticle.id).desc()).first()

    peak_reading_time = f"{peak_time_query[0]}:00" if peak_time_query else 'N/A'

    # Get other stats with default values
    total_articles = db.session.query(func.count(ReadArticle.id)).filter_by(user_id=user_id).scalar() or 0
    bookmarks_count = db.session.query(func.count(Bookmark.id)).filter_by(user_id=user_id).scalar() or 0
    
    # Calculate average articles per day
    first_read = db.session.query(func.min(ReadArticle.read_at)).filter_by(user_id=user_id).scalar()
    if first_read:
        days_since_first = (datetime.utcnow() - first_read).days or 1
        avg_articles = round(total_articles / days_since_first, 1)
    else:
        avg_articles = 0

    # Get favorite category
    favorite_category_query = db.session.query(
        ReadArticle.category,
        func.count(ReadArticle.id).label('count')
    ).filter_by(user_id=user_id).group_by(ReadArticle.category).order_by(func.count(ReadArticle.id).desc()).first()

    favorite_category = favorite_category_query[0] if favorite_category_query else 'N/A'

    # Get articles read today
    today = datetime.utcnow().date()
    articles_today = db.session.query(func.count(ReadArticle.id)).filter(
        ReadArticle.user_id == user_id,
        func.date(ReadArticle.read_at) == today
    ).scalar() or 0

    # Get longest streak
    longest_streak = db.session.query(User.longest_streak).filter_by(id=user_id).first()
    longest_streak = longest_streak[0] if longest_streak else 0

    # Calculate current streak
    current_streak = calculate_streak(user_id)  # Make sure this function exists

    return {
        'most_active_day': most_active_day,
        'peak_reading_time': peak_reading_time,
        'total_articles': total_articles,
        'bookmarks_count': bookmarks_count,
        'avg_articles_per_day': avg_articles,
        'favorite_category': favorite_category,
        'articles_today': articles_today,
        'longest_streak': longest_streak,
        'streak': current_streak
    }

def get_top_categories(user_id):
    """Get top categories with their percentages"""
    categories = db.session.query(
        ReadArticle.category,
        func.count().label('count')
    ).filter(
        ReadArticle.user_id == user_id,
        ReadArticle.category.isnot(None)
    ).group_by(
        ReadArticle.category
    ).order_by(db.desc('count')).all()
    
    total = sum(cat[1] for cat in categories)
    return [
        {
            'name': cat[0],
            'count': cat[1],
            'percentage': round((cat[1] / total) * 100 if total > 0 else 0)
        }
        for cat in categories[:5]  # Top 5 categories
    ]

@app.route("/")
def home():
    if current_user.is_authenticated:
        stats = get_user_stats(current_user.id)
        return render_template(
            "home_loggedIn.html",
            user=current_user,
            stats=stats,
            countries=COUNTRIES
        )
    return render_template("home.html")  # Keep the original landing page

@app.route("/guest_news")
def guest_news():
    # Create form instance for guest users
    form = NewsFilterForm()
    
    keywords = request.args.get('keywords', '')
    category = request.args.get('category', '')
    
    # Build the API URL
    url = f"https://newsapi.org/v2/top-headlines?apiKey={NEWS_API_KEY}&language=en"
    if category:
        url += f"&category={category}"
    if keywords:
        url += f"&q={keywords}"
    
    try:
        response = requests.get(url)
        if response.ok:
            articles = response.json().get('articles', [])
            return render_template('news.html', articles=articles, form=form, is_guest=True)
    except Exception as e:
        print(f"Error fetching news: {e}")
    
    return render_template('news.html', articles=[], form=form, is_guest=True)

@app.route("/get_trending_articles")
def get_trending_articles():
    try:
        url = f"https://newsapi.org/v2/top-headlines?apiKey={NEWS_API_KEY}&pageSize=6&language=en"
        response = requests.get(url)
        if response.ok:
            return jsonify({'articles': response.json().get('articles', [])})
    except Exception as e:
        print(f"Error fetching trending articles: {e}")
    return jsonify({'articles': []})

@app.route('/set_theme', methods=['POST'])
def set_theme():
    if not request.is_json:
        return jsonify({'error': 'Invalid content type'}), 400
        
    data = request.get_json()
    theme = data.get('theme')
    
    if theme not in ['light', 'dark']:
        return jsonify({'error': 'Invalid theme'}), 400
        
    # Store theme in session
    session['theme'] = theme
    
    # If user is logged in, store theme in database
    if current_user.is_authenticated:
        current_user.theme = theme
        db.session.commit()
    
    return jsonify({'status': 'success', 'theme': theme})

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    form = LoginForm()  # Create the form instance
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        else:
            flash('Invalid username or password', 'error')
            
    return render_template('login.html', form=form)  # Pass form to template

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

@app.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        signup_errors = []
        if User.query.filter_by(username=username).first():
            signup_errors.append("Username already exists.")
        if len(username) < 3 or not username.isalnum():
            signup_errors.append("Username must be at least 3 characters long and alphanumeric.")
        if len(password) < 8:
            signup_errors.append("Password must be at least 8 characters long.")

        if not signup_errors:
            hashed_password = generate_password_hash(password)
            # Make the first user an admin
            is_first_user = User.query.count() == 0
            print(f"Creating new user. Is first user? {is_first_user}")  # Debug print
            
            new_user = User(
                username=username, 
                password_hash=hashed_password,
                is_admin=is_first_user
            )
            db.session.add(new_user)
            db.session.commit()
            
            print(f"Created user {username} with admin status: {new_user.is_admin}")  # Debug print
            flash('Account created successfully!', 'success')
            return redirect(url_for("login"))
        
        return render_template("signup.html", form=form, signup_errors=signup_errors)
    
    return render_template("signup.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.before_request
def apply_universal_theme():
    if current_user.is_authenticated:
        # First check for user-specific theme
        if current_user.theme:
            session['theme'] = current_user.theme
            g.theme = current_user.theme
            return
            
        # Then check for universal theme
        settings = GlobalSettings.query.first()
        if settings and settings.universal_theme:
            session['theme'] = settings.universal_theme
            g.universal_theme = settings.universal_theme
        else:
            # Clear theme if neither exists
            if 'theme' in session:
                del session['theme']

@app.context_processor
def inject_theme():
    # Inject both user theme and universal theme
    return {
        'theme': getattr(g, 'theme', None),
        'universal_theme': getattr(g, 'universal_theme', None)
    }

@app.route('/view_article')
def view_article():
    url = request.args.get('url')
    title = request.args.get('title')
    category = request.args.get('category')
    mode = request.args.get('mode', 'prompt')
    
    if not url:
        return redirect(url_for('get_news'))
    
    # Only track views and update stats for logged-in users
    if current_user.is_authenticated:
        # Record article view
        article_view = ArticleView(
            user_id=current_user.id,
            article_url=url,
            article_title=title,
            category=category
        )
        db.session.add(article_view)
        
        # Add ReadArticle record for streak tracking
        read_article = ReadArticle(
            user_id=current_user.id,
            article_url=url,
            article_title=title,
            category=category,
            read_at=datetime.utcnow()
        )
        db.session.add(read_article)
        db.session.commit()

    # Reader mode functionality available to all users
    if mode == 'reader':
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            def is_valid_image(img_url):
                try:
                    img_response = requests.head(img_url, timeout=2)
                    content_type = img_response.headers.get('content-type', '')
                    content_length = img_response.headers.get('content-length')
                    
                    # Check if it's an image and has reasonable size (>1KB)
                    is_image = content_type.startswith('image/')
                    has_size = content_length and int(content_length) > 1000
                    
                    return is_image and has_size
                except:
                    return False

            # Remove unwanted elements first
            for element in soup(['script', 'style', 'meta', 'link', 'noscript', 'iframe', 'button', 
                              'input', 'form', 'nav', 'header', 'footer']):
                element.decompose()

            # Find main article content (same selectors as before)
            article_content = None
            content_selectors = [
                '[data-testid="article-body"]',
                '[data-testid="article-content"]',
                '.article__body',
                '.article-body',
                '.article__content',
                '.article-content',
                '.story__body',
                '.story-body',
                '.post-content',
                '.entry-content',
                '.main-content',
                'article',
                '.article',
                'main'
            ]
            
            for selector in content_selectors:
                potential_content = soup.select_one(selector)
                if potential_content and potential_content.find_all('p'):
                    article_content = potential_content
                    break
            
            if not article_content:
                # Fallback to largest paragraph cluster
                all_paragraphs = soup.find_all('p')
                if all_paragraphs:
                    parent_count = {}
                    for p in all_paragraphs:
                        if p.parent:
                            parent_count[p.parent] = parent_count.get(p.parent, 0) + 1
                    if parent_count:
                        article_content = max(parent_count.keys(), key=lambda x: parent_count[x])
            
            if article_content:
                # Create clean container
                clean_content = soup.new_tag('div')
                
                # Process paragraphs and images
                for element in article_content.find_all(['p', 'img', 'figure']):
                    if element.name == 'p':
                        # Keep non-empty paragraphs
                        if element.get_text(strip=True):
                            new_p = soup.new_tag('p')
                            new_p.string = element.get_text(strip=True)
                            clean_content.append(new_p)
                    
                    elif element.name == 'img':
                        # Process and validate direct images
                        if element.get('src'):
                            img_url = urljoin(url, element.get('src'))
                            if is_valid_image(img_url):
                                new_img = soup.new_tag('img')
                                new_img['src'] = img_url
                                new_img['loading'] = 'lazy'
                                if element.get('alt'):
                                    new_img['alt'] = element.get('alt')
                                clean_content.append(new_img)
                    
                    elif element.name == 'figure':
                        # Handle and validate images within figures
                        img = element.find('img')
                        if img and img.get('src'):
                            img_url = urljoin(url, img.get('src'))
                            if is_valid_image(img_url):
                                new_img = soup.new_tag('img')
                                new_img['src'] = img_url
                                new_img['loading'] = 'lazy'
                                if img.get('alt'):
                                    new_img['alt'] = img.get('alt')
                                
                                # Add caption if exists
                                caption = element.find(['figcaption', 'caption'])
                                if caption and caption.get_text(strip=True):
                                    new_p = soup.new_tag('p')
                                    new_p['class'] = 'image-caption'
                                    new_p.string = caption.get_text(strip=True)
                                    
                                    clean_content.append(new_img)
                                    clean_content.append(new_p)
                                else:
                                    clean_content.append(new_img)
                
                article_content = clean_content
                
                # Debug info
                print(f"Found {len(article_content.find_all('p'))} paragraphs and {len(article_content.find_all('img'))} valid images")
                
            return render_template('reader_mode.html', 
                                 content=article_content, 
                                 title=title,
                                 original_url=url)
        except Exception as e:
            print(f"Error in reader mode: {e}")
            return redirect(url)
    
    # For normal mode, redirect to the article URL
    return redirect(url)

def extract_topics(articles, num_topics=5):
    """Extract main topics from articles using TF-IDF and clustering"""
    # Combine title and description for better topic extraction
    texts = [f"{a.get('title', '')} {a.get('description', '')}" for a in articles]
    
    # TF-IDF vectorization
    vectorizer = TfidfVectorizer(
        stop_words='english',
        max_features=1000,
        ngram_range=(1, 2)
    )
    tfidf_matrix = vectorizer.fit_transform(texts)
    
    # Cluster into topics
    kmeans = KMeans(n_clusters=num_topics)
    kmeans.fit(tfidf_matrix)
    
    # Get top terms for each cluster
    order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
    terms = vectorizer.get_feature_names_out()
    
    # Assign topics to articles
    clusters = kmeans.predict(tfidf_matrix)
    for article, cluster in zip(articles, clusters):
        article['topic'] = [terms[i] for i in order_centroids[cluster, :3]]
    
    return articles

def get_content_recommendations(user_history, limit=20):
    """Get content-based recommendations based on user's reading history"""
    if not user_history:
        # Default recommendations if no history
        url = f"https://newsapi.org/v2/top-headlines?apiKey={NEWS_API_KEY}&pageSize={limit}&language=en"
        response = requests.get(url)
        return response.json().get('articles', []) if response.ok else []
    
    # Get user's preferred categories
    categories = [h.category for h in user_history if h.category]
    if categories:
        url = f"https://newsapi.org/v2/top-headlines"
        articles = []
        for category in set(categories):
            params = {
                'apiKey': NEWS_API_KEY,
                'category': category,
                'pageSize': limit // len(set(categories)),
                'language': 'en'
            }
            response = requests.get(url, params=params)
            if response.ok:
                articles.extend(response.json().get('articles', []))
        return articles
    return []

def merge_recommendations(collab_articles, content_articles):
    """Merge and deduplicate recommendations"""
    seen_urls = set()
    merged = []
    
    for article in collab_articles + content_articles:
        url = article.get('url')
        if url and url not in seen_urls:
            seen_urls.add(url)
            merged.append(article)
    
    return merged

def get_collaborative_recommendations(similar_users, limit=20):
    """Get recommendations based on similar users' reading history"""
    if not similar_users:
        return []
        
    # Get articles read by similar users recently
    recent_articles = ReadArticle.query.filter(
        ReadArticle.user_id.in_(similar_users),
        ReadArticle.read_at >= datetime.utcnow() - timedelta(days=7)
    ).all()
    
    # Convert to news API format
    articles = []
    for article in recent_articles:
        articles.append({
            'title': article.article_title,
            'url': article.article_url,
            'publishedAt': article.read_at.strftime('%Y-%m-%dT%H:%M:%SZ')
        })
    
    return articles[:limit]

def estimate_reading_time(text):
    """Estimate reading time in minutes"""
    words = len(text.split())
    return max(1, round(words / 200))  # Assume 200 words per minute

def get_trending_topics():
    """Get trending topics from recent articles"""
    recent_articles = ReadArticle.query.filter(
        ReadArticle.read_at >= datetime.utcnow() - timedelta(hours=24)
    ).limit(100).all()
    
    # Extract and count topics
    topic_counts = defaultdict(int)
    for article in recent_articles:
        if article.topic:
            for topic in article.topic:
                topic_counts[topic] += 1
    
    # Return top 5 trending topics
    return sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]

@app.route("/bookmark_article", methods=["POST"])
@login_required
def bookmark_article():
    data = request.get_json()
    url = data.get('url')
    title = data.get('title')
    
    if not url:
        return jsonify({'error': 'URL required'}), 400
    
    # Check if article already exists
    existing_article = ReadArticle.query.filter_by(
        user_id=current_user.id,
        article_url=url
    ).first()
    
    if existing_article:
        # Update existing article
        existing_article.bookmarked = True
        existing_article.read_at = datetime.utcnow()
        if title:  # Update title if provided
            existing_article.article_title = title
    else:
        # Create new article
        article = ReadArticle(
            user_id=current_user.id,
            article_url=url,
            article_title=title,
            read_at=datetime.utcnow(),
            bookmarked=True
        )
        db.session.add(article)
    
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route("/get_reading_history")
@login_required
def get_reading_history():
    # Use a subquery to get the latest read_at for each article
    latest_reads = db.session.query(
        ReadArticle.article_url,
        func.max(ReadArticle.read_at).label('latest_read')
    ).filter(
        ReadArticle.user_id == current_user.id
    ).group_by(
        ReadArticle.article_url
    ).subquery()
    
    # Join to get full article details
    history = db.session.query(ReadArticle).join(
        latest_reads,
        db.and_(
            ReadArticle.article_url == latest_reads.c.article_url,
            ReadArticle.read_at == latest_reads.c.latest_read
        )
    ).order_by(
        ReadArticle.read_at.desc()
    ).limit(10).all()
    
    return jsonify({
        'history': [{
            'title': h.article_title,
            'url': h.article_url,
            'read_at': h.read_at.strftime("%Y-%m-%d %H:%M"),
            'bookmarked': h.bookmarked
        } for h in history]
    })

@app.route("/bookmarks")
@login_required
def bookmarks():
    return render_template("bookmarks.html")

@app.route("/get_bookmarks")
@login_required
def get_bookmarks():
    bookmarks = ReadArticle.query.filter_by(
        user_id=current_user.id,
        bookmarked=True
    ).order_by(ReadArticle.read_at.desc()).all()
    
    return jsonify({
        'bookmarks': [{
            'title': b.article_title,
            'url': b.article_url,
            'bookmarked_at': b.read_at.strftime("%Y-%m-%d %H:%M:%S")
        } for b in bookmarks]
    })

@app.route("/remove_bookmark", methods=["POST"])
@login_required
def remove_bookmark():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL required'}), 400
        
    bookmark = ReadArticle.query.filter_by(
        user_id=current_user.id,
        article_url=url,
        bookmarked=True
    ).first()
    
    if bookmark:
        bookmark.bookmarked = False
        db.session.commit()
    
    return jsonify({'status': 'success'})

@app.route("/reading_history")
@login_required
def reading_history():
    # Use a subquery to get the latest read_at for each article
    latest_reads = db.session.query(
        ReadArticle.article_url,
        func.max(ReadArticle.read_at).label('latest_read')
    ).filter(
        ReadArticle.user_id == current_user.id
    ).group_by(
        ReadArticle.article_url
    ).subquery()
    
    # Join with original table to get full article details
    history = db.session.query(ReadArticle).join(
        latest_reads,
        db.and_(
            ReadArticle.article_url == latest_reads.c.article_url,
            ReadArticle.read_at == latest_reads.c.latest_read
        )
    ).order_by(
        ReadArticle.read_at.desc()
    ).all()
    
    return render_template("reading_history.html", history=history)

def check_streak_rewards(user_id):
    stats = get_user_stats(user_id)
    streak = stats['streak']
    user = User.query.get(user_id)
    
    # Convert string to list if needed
    if isinstance(user.unlocked_themes, str):
        user.unlocked_themes = user.unlocked_themes.split(',') if user.unlocked_themes else []
    
    # Check streak milestones and unlock themes
    if streak >= 1 and 'mono' not in user.unlocked_themes:
        user.unlocked_themes.append('mono')
    if streak >= 7 and 'sunset' not in user.unlocked_themes:
        user.unlocked_themes.append('sunset')
    if streak >= 14 and 'ocean' not in user.unlocked_themes:
        user.unlocked_themes.append('ocean')
    if streak >= 30 and 'forest' not in user.unlocked_themes:
        user.unlocked_themes.append('forest')
    
    # Save changes
    if user.unlocked_themes:
        user.unlocked_themes = ','.join(user.unlocked_themes)
        db.session.commit()

@app.route("/dashboard")
@login_required
def dashboard():
    today = datetime.utcnow().date()
    stats = get_user_stats(current_user.id)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Get reading history by category - fixed to handle NULL categories
    category_stats = db.session.query(
        func.coalesce(ReadArticle.category, 'Uncategorized').label('category'),
        func.count(ReadArticle.id).label('count')
    ).filter(
        ReadArticle.user_id == current_user.id,
        ReadArticle.read_at >= thirty_days_ago
    ).group_by('category').all()
    
    # Format data for charts - use list comprehension with default for empty results
    categories = [cat[0] for cat in category_stats] if category_stats else ['No Data']
    category_counts = [cat[1] for cat in category_stats] if category_stats else [1]
    
    # Get dates for the chart
    dates = [(today - timedelta(days=x)).strftime('%b %d') for x in range(29, -1, -1)]
    
    # Get reading counts per day and format as a dictionary
    daily_reads = db.session.query(
        func.date(ReadArticle.read_at).label('date'),
        func.count(ReadArticle.id).label('count')
    ).filter(
        ReadArticle.user_id == current_user.id,
        ReadArticle.read_at >= thirty_days_ago
    ).group_by('date').all()
    
    # Convert to dictionary for easier lookup
    reads_by_date = {str(row[0]): row[1] for row in daily_reads}
    
    # Create daily counts array matching the dates array
    daily_counts = []
    for i in range(29, -1, -1):
        date_str = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        daily_counts.append(reads_by_date.get(date_str, 0))
    
    # Recent activity
    recent_articles = ReadArticle.query.filter_by(user_id=current_user.id)\
        .order_by(ReadArticle.read_at.desc())\
        .limit(10).all()
    
    return render_template(
        'dashboard.html',
        stats=stats,
        categories=categories,
        category_counts=category_counts,
        dates=dates,
        daily_counts=daily_counts,
        recent_articles=recent_articles,
        streak=calculate_streak(current_user.id)
    )

def calculate_longest_streak(user_id):
    """Calculate user's longest reading streak"""
    articles = ReadArticle.query.filter_by(user_id=user_id).order_by(ReadArticle.read_at.desc()).all()
    if not articles:
        return 0
        
    longest_streak = current_streak = 1
    current_date = articles[0].read_at.date()
    
    for article in articles[1:]:
        article_date = article.read_at.date()
        if (current_date - article_date).days == 1:
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        elif (current_date - article_date).days > 1:
            current_streak = 1
        current_date = article_date
        
    return longest_streak

def get_favorite_category(user_id):
    """Get user's most read category"""
    favorite = db.session.query(
        ReadArticle.category,
        func.count(ReadArticle.category).label('count')
    ).filter(
        ReadArticle.user_id == user_id,
        ReadArticle.category.isnot(None)
    ).group_by(
        ReadArticle.category
    ).order_by(db.desc('count')).first()
    
    return favorite[0] if favorite else 'None'

def calculate_streak(user_id):
    """Calculate current reading streak"""
    today = datetime.utcnow().date()
    streak = 0
    current_date = today
    
    while True:
        has_read = ReadArticle.query.filter(
            ReadArticle.user_id == user_id,
            func.date(ReadArticle.read_at) == current_date
        ).first()
        if not has_read:
            break
        streak += 1
        current_date -= timedelta(days=1)
    
    return streak

@app.route('/save_dashboard_layout', methods=['POST'])
@login_required
def save_dashboard_layout():
    layout = request.get_json()
    current_user.dashboard_layout = json.dumps(layout)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

def fetch_news(category=None, keywords=None, country=None):
    """Fetch news articles from the API"""
    base_url = "https://newsapi.org/v2/top-headlines"
    params = {
        'apiKey': NEWS_API_KEY,
        'pageSize': 30
    }
    
    if category:
        params['category'] = category
    if keywords:
        params['q'] = keywords
    if country:
        params['country'] = country
    else:
        params['country'] = 'us'  # default to US news
        
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        return data.get('articles', [])
    except:
        return []

@app.route('/test_csrf', methods=['GET', 'POST'])
def test_csrf():
    if request.method == 'POST':
        return "CSRF token is valid!"
    return render_template('test_csrf.html')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need to be an admin to access this page.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    # Get all users
    users = User.query.all()
    
    # Get total articles read
    total_articles = db.session.query(func.count(ReadArticle.id)).scalar()
    
    # Get active users in last 24h
    active_users = db.session.query(func.count(User.id)).filter(
        User.last_login >= datetime.utcnow() - timedelta(hours=24)
    ).scalar()
    
    return render_template(
        'admin/dashboard.html',
        users=users,
        total_articles=total_articles,
        active_users=active_users
    )

@app.route("/admin/make_admin/<int:user_id>", methods=['POST'])
@login_required
@admin_required
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    flash(f'Made {user.username} an admin', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/remove_admin/<int:user_id>", methods=['POST'])
@login_required
@admin_required
def remove_admin(user_id):
    if user_id == current_user.id:
        flash('You cannot remove your own admin status', 'error')
        return redirect(url_for('admin_dashboard'))
        
    user = User.query.get_or_404(user_id)
    user.is_admin = False
    db.session.commit()
    flash(f'Removed admin status from {user.username}', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/delete_user/<int:user_id>", methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin_dashboard'))
        
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Deleted user {user.username}', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/articles")
@login_required
@admin_required
def manage_articles():
    # Get all article views with user information
    article_views = db.session.query(
        ArticleView,
        func.count(ArticleView.id).label('view_count'),
        func.max(ArticleView.viewed_at).label('last_viewed')
    ).group_by(
        ArticleView.article_url
    ).order_by(
        func.max(ArticleView.viewed_at).desc()
    ).all()
    
    # Get bookmark counts for each article
    bookmark_counts = db.session.query(
        ReadArticle.article_url,
        func.count(ReadArticle.id).label('bookmark_count')
    ).filter(
        ReadArticle.bookmarked == True
    ).group_by(
        ReadArticle.article_url
    ).all()
    
    bookmark_dict = {url: count for url, count in bookmark_counts}
    
    articles_data = []
    for view, view_count, last_viewed in article_views:
        articles_data.append({
            'title': view.article_title,
            'url': view.article_url,
            'category': view.category,
            'view_count': view_count,
            'last_viewed': last_viewed,
            'bookmark_count': bookmark_dict.get(view.article_url, 0)
        })
    
    return render_template(
        'admin/articles.html',
        articles=articles_data
    )

@app.route("/admin/articles/approve/<int:article_id>", methods=['POST'])
@login_required
@admin_required
def approve_article(article_id):
    article = ManagedArticle.query.get_or_404(article_id)
    article.is_approved = True
    article.approved_by = current_user.id
    article.approved_at = datetime.utcnow()
    db.session.commit()
    flash(f'Approved article: {article.title}', 'success')
    return redirect(url_for('manage_articles'))

@app.route("/admin/articles/feature/<int:article_id>", methods=['POST'])
@login_required
@admin_required
def feature_article(article_id):
    article = ManagedArticle.query.get_or_404(article_id)
    article.is_featured = not article.is_featured  # Toggle featured status
    db.session.commit()
    flash(f'{"Featured" if article.is_featured else "Unfeatured"} article: {article.title}', 'success')
    return redirect(url_for('manage_articles'))

@app.route("/admin/sources")
@login_required
@admin_required
def manage_sources():
    sources = NewsSource.query.order_by(NewsSource.name).all()
    
    # Enhance source data with website info
    sources_data = []
    for source in sources:
        try:
            domain = urlparse(source.url).netloc
            website_info = {
                'name': source.name,
                'url': source.url,
                'domain': domain,
                'category': source.category,
                'is_active': source.is_active,
                'credibility_score': source.credibility_score,
                'last_fetched': source.last_fetched,
                'status': check_website_status(source.url),
                'article_count': ArticleView.query.filter(
                    ArticleView.article_url.like(f"%{domain}%")
                ).count(),
                'total_views': db.session.query(func.count(ArticleView.id)).filter(
                    ArticleView.article_url.like(f"%{domain}%")
                ).scalar() or 0
            }
            sources_data.append(website_info)
        except Exception as e:
            print(f"Error processing source {source.name}: {e}")
            continue
    
    return render_template(
        'admin/sources.html',
        sources=sources_data
    )

def check_website_status(url):
    try:
        response = requests.head(url, timeout=5)
        if response.status_code == 200:
            return {'status': 'Online', 'code': 200}
        else:
            return {'status': 'Issues', 'code': response.status_code}
    except:
        return {'status': 'Offline', 'code': 0}

@app.route("/admin/sources/add", methods=['GET', 'POST'])
@login_required
@admin_required
def add_source():
    if request.method == 'POST':
        source = NewsSource(
            name=request.form['name'],
            url=request.form['url'],
            api_key=request.form.get('api_key'),
            category=request.form.get('category'),
            added_by=current_user.id
        )
        db.session.add(source)
        db.session.commit()
        flash(f'Added news source: {source.name}', 'success')
        return redirect(url_for('manage_sources'))
    return render_template('admin/add_source.html')

@app.route("/admin/sources/edit/<int:source_id>", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_source(source_id):
    source = NewsSource.query.get_or_404(source_id)
    if request.method == 'POST':
        source.name = request.form['name']
        source.url = request.form['url']
        source.api_key = request.form.get('api_key')
        source.category = request.form.get('category')
        source.is_active = 'is_active' in request.form
        source.credibility_score = float(request.form.get('credibility_score', 0))
        db.session.commit()
        flash(f'Updated news source: {source.name}', 'success')
        return redirect(url_for('manage_sources'))
    return render_template('admin/edit_source.html', source=source)

@app.route("/admin/article_details")
@login_required
@admin_required
def article_details():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL required'}), 400
        
    # Get article views
    views = ArticleView.query.filter_by(article_url=url).all()
    unique_viewers = db.session.query(ArticleView.user_id).filter_by(article_url=url).distinct().count()
    
    # Get bookmarks
    bookmarks = ReadArticle.query.filter_by(article_url=url, bookmarked=True).count()
    total_reads = ReadArticle.query.filter_by(article_url=url).count()
    bookmark_rate = (bookmarks / total_reads * 100) if total_reads > 0 else 0
    
    # Get recent viewers
    recent_viewers = db.session.query(
        User.username,
        ArticleView.viewed_at
    ).join(User).filter(
        ArticleView.article_url == url
    ).order_by(
        ArticleView.viewed_at.desc()
    ).limit(5).all()
    
    return jsonify({
        'total_views': len(views),
        'unique_viewers': unique_viewers,
        'bookmark_rate': round(bookmark_rate, 1),
        'avg_view_time': 0,  # You could add view time tracking if needed
        'recent_viewers': [
            {
                'username': viewer.username,
                'viewed_at': viewer.viewed_at.strftime('%Y-%m-%d %H:%M')
            }
            for viewer in recent_viewers
        ]
    })

@app.route("/admin/source_details")
@login_required
@admin_required
def source_details():
    domain = request.args.get('domain')
    if not domain:
        return jsonify({'error': 'Domain required'}), 400
    
    # Get articles from this source in the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Get recent articles
    recent_articles = db.session.query(
        ArticleView.article_title,
        func.count(ArticleView.id).label('views')
    ).filter(
        ArticleView.article_url.like(f"%{domain}%"),
        ArticleView.viewed_at >= thirty_days_ago
    ).group_by(
        ArticleView.article_title
    ).order_by(
        func.count(ArticleView.id).desc()
    ).limit(5).all()
    
    # Calculate average daily views
    total_views = db.session.query(func.count(ArticleView.id)).filter(
        ArticleView.article_url.like(f"%{domain}%"),
        ArticleView.viewed_at >= thirty_days_ago
    ).scalar() or 0
    avg_daily_views = round(total_views / 30, 1)
    
    # Get most popular category
    popular_category = db.session.query(
        ArticleView.category,
        func.count(ArticleView.id).label('count')
    ).filter(
        ArticleView.article_url.like(f"%{domain}%"),
        ArticleView.category.isnot(None)
    ).group_by(
        ArticleView.category
    ).order_by(
        func.count(ArticleView.id).desc()
    ).first()
    
    # Calculate engagement rate (views to bookmarks ratio)
    bookmarks = ReadArticle.query.filter(
        ReadArticle.article_url.like(f"%{domain}%"),
        ReadArticle.bookmarked == True
    ).count()
    
    engagement_rate = round((bookmarks / total_views * 100) if total_views > 0 else 0, 1)
    
    return jsonify({
        'avg_daily_views': avg_daily_views,
        'popular_category': popular_category[0] if popular_category else 'N/A',
        'engagement_rate': engagement_rate,
        'recent_articles': [
            {
                'title': article.article_title,
                'views': article.views
            }
            for article in recent_articles
        ]
    })

@app.route("/admin/theme", methods=['POST'])
@login_required
@admin_required
def set_universal_theme():
    theme = request.form.get('theme')
    settings = GlobalSettings.query.first()
    
    if settings:
        if theme:
            # Update theme
            settings.universal_theme = theme
            settings.set_by = current_user.id
            settings.set_at = datetime.utcnow()
            flash(f'Universal theme set to {theme}', 'success')
        else:
            # Remove universal theme
            settings.universal_theme = None
            settings.set_by = current_user.id
            settings.set_at = datetime.utcnow()
            flash('Universal theme removed', 'success')
    else:
        # Create new settings if none exist
        if theme:
            settings = GlobalSettings(
                universal_theme=theme,
                set_by=current_user.id
            )
            db.session.add(settings)
            flash(f'Universal theme set to {theme}', 'success')
    
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route("/admin/user/<int:user_id>/theme", methods=['POST'])
@login_required
@admin_required
def set_user_theme(user_id):
    user = User.query.get_or_404(user_id)
    theme = request.form.get('theme')
    
    # Update user's theme
    user.theme = theme
    # Reset their unlocked themes to include the new theme if it's special
    if theme in ['sunset', 'ocean', 'forest']:
        current_themes = set(user.unlocked_themes.split(',') if user.unlocked_themes else [])
        current_themes.add(theme)
        user.unlocked_themes = ','.join(current_themes)
    
    db.session.commit()
    flash(f'Updated theme for user {user.username}', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route("/read_article")
def read_article():
    url = request.args.get('url')
    title = request.args.get('title')
    category = request.args.get('category')  # Add this to capture category
    preview_image = request.args.get('preview_image')  # Initialize preview_image variable
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
        
    # Track article view if user is logged in
    if current_user.is_authenticated:
        # Record article view
        article_view = ArticleView(
            user_id=current_user.id,
            article_url=url,
            article_title=title,
            category=category,
            viewed_at=datetime.utcnow()
        )
        db.session.add(article_view)
        
        # Add or update ReadArticle record
        existing_read = ReadArticle.query.filter_by(
            user_id=current_user.id,
            article_url=url
        ).first()
        
        if existing_read:
            existing_read.read_at = datetime.utcnow()
            if title:  # Update title if provided
                existing_read.article_title = title
            if category and not existing_read.category:  # Update category if not set
                existing_read.category = category
        else:
            read_article = ReadArticle(
                user_id=current_user.id,
                article_url=url,
                article_title=title,
                category=category,
                read_at=datetime.utcnow()
            )
            db.session.add(read_article)
        
        try:
            db.session.commit()
        except Exception as e:
            print(f"Error recording article view: {e}")
            db.session.rollback()
    
    try:
        # Fetch article content with headers to avoid blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract main content
        article_content = []
        images = []
        
        # Try to find article content using common selectors
        content_selectors = [
            'article',
            '[data-testid="article-body"]',
            '.article-content',
            '.article-body',
            '.story-content',
            '.story-body',
            '.post-content',
            '.entry-content',
            '.content-body',
            '.article__body',
            '.article__content',
            'main',
            '#main-content',
            '.main-content'
        ]
        main_content = None
        
        for selector in content_selectors:
            content = soup.select(selector)
            content = content[0] if content else None
            if content:
                main_content = content
                break
        
        if main_content:
            # Remove unwanted elements
            for unwanted in main_content.select('script, style, nav, header, footer, .ad, .advertisement, .social-share, .newsletter, .share, .related-articles, .sidebar, aside'):
                unwanted.decompose()
            
            # Validate preview image first if available
            if preview_image and not any(skip in preview_image.lower() for skip in [
                'icon', 'logo', 'avatar', 'thumb',
                'placeholder', 'default', 'blank',
                'bbcx/grey-placeholder',
                'pixel.gif', 'spacer.gif'
            ]):
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    img_response = requests.head(preview_image, headers=headers, timeout=2)
                    content_type = img_response.headers.get('content-type', '')
                    content_length = img_response.headers.get('content-length')
                    
                    if content_type.startswith('image/') and content_length and int(content_length) > 1000:
                        images.append({
                            'src': preview_image,
                            'alt': title,
                            'caption': ''
                        })
                except:
                    pass
            
            # Extract article images if preview image wasn't valid
            if not images:
                for img in main_content.find_all('img'):
                    src = img.get('src', '')
                    if src:
                        if not src.startswith('http'):
                            src = urljoin(url, src)
                        if any(skip in src.lower() for skip in [
                            'icon', 'logo', 'avatar', 'thumb',
                            'placeholder', 'default', 'blank',
                            'bbcx/grey-placeholder',
                            'pixel.gif', 'spacer.gif'
                        ]):
                            continue
                        
                        try:
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            }
                            img_response = requests.head(src, headers=headers, timeout=2)
                            content_type = img_response.headers.get('content-type', '')
                            content_length = img_response.headers.get('content-length')
                            
                            if content_type.startswith('image/') and content_length and int(content_length) > 1000:
                                parsed = urlparse(src)
                                if not parsed.scheme:
                                    src = f"https:{src}" if src.startswith('//') else urljoin(url, src)
                                images.append({
                                    'src': src,
                                    'alt': img.get('alt', ''),
                                    'caption': img.get('caption', '') or img.find_next('figcaption').text if img.find_next('figcaption') else ''
                                })
                                break
                        except:
                            continue
            
            # If no valid image found and we have a preview image, use it
            if not images and preview_image:
                if not any(skip in preview_image.lower() for skip in [
                    'placeholder', 'default', 'blank',
                    'bbcx/grey-placeholder',
                    'pixel.gif', 'spacer.gif'
                ]):
                    images.append({
                        'src': preview_image,
                        'alt': title,
                        'caption': ''
                    })
            
            # Extract paragraphs while preserving structure
            for element in main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote']):
                # Skip empty elements or those containing only whitespace/special characters
                text = element.get_text(strip=True)
                if text and not text.isspace() and len(text) > 1:
                    # Skip elements that are likely navigation/metadata
                    if any(skip in str(element.get('class', [])).lower() for skip in ['nav', 'menu', 'share', 'meta', 'tag']):
                        continue
                    article_content.append({
                        'type': element.name,
                        'content': text
                    })
        else:
            # Fallback to basic paragraph extraction
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if text and not text.isspace() and len(text) > 1:
                    if not any(skip in str(p.get('class', [])).lower() for skip in ['nav', 'menu', 'share', 'meta', 'tag']):
                        paragraphs.append({
                            'type': 'p',
                            'content': text
                        })
            article_content = paragraphs
            
            # Use preview image if available
            if preview_image:
                images.append({
                    'src': preview_image,
                    'alt': title,
                    'caption': ''
                })
        
        # After content extraction, check if we actually got any content
        if not article_content or len(article_content) < 2:
            return render_template('article_reader_error.html',
                                 title=title,
                                 original_url=url,
                                 error_message="Couldn't extract article content. This might be due to the website's structure or content protection.")
        
        return render_template('article_reader.html',
                             title=title,
                             content=article_content,
                             images=images,
                             source_url=url)
                             
    except Exception as e:
        return render_template('article_reader_error.html',
                             title=title,
                             original_url=url,
                             error_message=f"An error occurred while trying to read this article: {str(e)}")

@app.route("/toggle_bookmark", methods=["POST"])
@login_required
def toggle_bookmark():
    data = request.get_json()
    url = data.get('url')
    title = data.get('title')
    category = data.get('category', 'general')
    
    if not url or not title:
        return jsonify({'error': 'URL and title required'}), 400
    
    # Check if article already exists
    existing_article = ReadArticle.query.filter_by(
        user_id=current_user.id,
        article_url=url
    ).first()
    
    if existing_article:
        # Toggle bookmark status
        existing_article.bookmarked = not existing_article.bookmarked
        message = 'Bookmark removed' if not existing_article.bookmarked else 'Article bookmarked'
    else:
        # Create new bookmarked article
        new_article = ReadArticle(
            user_id=current_user.id,
            article_url=url,
            article_title=title,
            category=category,
            read_at=datetime.utcnow(),
            bookmarked=True
        )
        db.session.add(new_article)
        message = 'Article bookmarked'
    
    try:
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': message,
            'bookmarked': existing_article.bookmarked if existing_article else True
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False)
