import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
import joblib
import os

class RecommendationModel:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=5000,  # Limit features for better performance
            ngram_range=(1, 2)  # Use both unigrams and bigrams
        )
        self.user_profiles = defaultdict(list)
        self.article_vectors = None
        self.articles = []
        self.model_path = 'recommendation_model.joblib'
        
        # Load existing model if it exists
        if os.path.exists(self.model_path):
            self.load_model()

    def update_user_profile(self, user_id, search_query, article_data):
        """Update user profile with new search and article interactions"""
        # Create new interaction with weight
        new_interaction = {
            'query': search_query,
            'timestamp': article_data.get('timestamp'),
            'category': article_data.get('category'),
            'articles': article_data.get('articles', []),
            'weight': 1.0  # New interactions start with full weight
        }
        
        # Add new interaction
        self.user_profiles[user_id].append(new_interaction)
        
        # Decay weights of older interactions
        for i in range(len(self.user_profiles[user_id]) - 1):
            if 'weight' not in self.user_profiles[user_id][i]:
                self.user_profiles[user_id][i]['weight'] = 1.0
            self.user_profiles[user_id][i]['weight'] *= 0.9
        
        # Keep only last 50 interactions
        if len(self.user_profiles[user_id]) > 50:
            self.user_profiles[user_id] = self.user_profiles[user_id][-50:]
        
        self.save_model()

    def get_user_preferences(self, user_id):
        """Extract user preferences from their history"""
        if user_id not in self.user_profiles:
            return None
        
        # Combine all user's searches and article interactions with weights
        all_text = []
        categories = defaultdict(float)
        
        for interaction in self.user_profiles[user_id]:
            weight = interaction['weight']
            if interaction['query']:
                all_text.extend([interaction['query']] * int(weight * 10))
            if interaction['category']:
                categories[interaction['category']] += weight
            for article in interaction['articles']:
                if article.get('title'):
                    all_text.extend([article['title']] * int(weight * 5))
                if article.get('description'):
                    all_text.extend([article['description']] * int(weight * 3))
        
        # Get most frequent category
        preferred_category = max(categories.items(), key=lambda x: x[1])[0] if categories else None
        
        return {
            'text_profile': ' '.join(all_text),
            'preferred_category': preferred_category
        }

    def get_recommendations(self, user_id, available_articles, num_recommendations=6):
        """Get personalized recommendations for user"""
        try:
            # If no articles available, return empty list
            if not available_articles:
                return []

            # Get user preferences
            user_prefs = self.get_user_preferences(user_id)
            
            # If no user preferences, return random selection
            if not user_prefs:
                return available_articles[:num_recommendations]
            
            # Vectorize available articles
            article_texts = [
                f"{a.get('title', '')} {a.get('description', '')}"
                for a in available_articles
            ]
            
            if not article_texts:
                return available_articles[:num_recommendations]
            
            # Add user profile to get similarity
            all_texts = article_texts + [user_prefs.get('text_profile', '')]
            
            try:
                vectors = self.vectorizer.fit_transform(all_texts)
                
                # Calculate similarity between user profile and articles
                user_vector = vectors[-1]
                article_vectors = vectors[:-1]
                similarities = cosine_similarity(user_vector, article_vectors).flatten()
                
                # Get top articles
                top_indices = similarities.argsort()[-num_recommendations:][::-1]
                recommended_articles = [available_articles[i] for i in top_indices]
                
                return recommended_articles
                
            except Exception as e:
                print(f"Vectorization error: {e}")
                return available_articles[:num_recommendations]
                
        except Exception as e:
            print(f"Error in get_recommendations: {e}")
            return available_articles[:num_recommendations]

    def save_model(self):
        """Save model state"""
        try:
            model_state = {
                'user_profiles': dict(self.user_profiles),
                'vectorizer': self.vectorizer
            }
            joblib.dump(model_state, self.model_path)
        except Exception as e:
            print(f"Error saving model: {e}")

    def load_model(self):
        """Load model state"""
        try:
            model_state = joblib.load(self.model_path)
            self.user_profiles = defaultdict(list, model_state['user_profiles'])
            self.vectorizer = model_state['vectorizer']
        except Exception as e:
            print(f"Error loading model: {e}")