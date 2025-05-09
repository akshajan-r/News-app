from datetime import datetime, timedelta
import numpy as np
import random
from recommendation_model import RecommendationModel
import pandas as pd

def generate_synthetic_data(num_users=1000, num_articles=10000, interactions_per_user=50):
    """
    Generate synthetic user-article interaction data for training.
    Enhanced with timestamps, interaction types, and realistic user behavior patterns.
    """
    user_history = {}
    user_preferences = {}
    article_data = {}
    
    # Enhanced categories with subcategories
    categories = {
        'technology': ['software', 'hardware', 'ai', 'cybersecurity'],
        'sports': ['football', 'basketball', 'tennis', 'esports'],
        'politics': ['domestic', 'international', 'economy', 'policy'],
        'entertainment': ['movies', 'music', 'gaming', 'celebrity'],
        'business': ['startups', 'finance', 'marketing', 'leadership']
    }
    
    # Generate article data
    print("Generating article data...")
    base_date = datetime.now() - timedelta(days=30)
    for article_id in range(num_articles):
        category = random.choice(list(categories.keys()))
        subcategory = random.choice(categories[category])
        article_data[article_id] = {
            'category': category,
            'subcategory': subcategory,
            'publish_date': base_date + timedelta(
                days=random.randint(0, 29),
                hours=random.randint(0, 23)
            ),
            'popularity': random.uniform(0.1, 1.0)
        }
    
    # Generate user preferences and interactions
    print("Generating user interactions...")
    for user_id in range(num_users):
        # Assign 1-3 preferred categories with weights
        num_preferred = random.randint(1, 3)
        preferred_cats = random.sample(list(categories.keys()), num_preferred)
        user_preferences[user_id] = {
            'categories': preferred_cats,
            'activity_level': random.uniform(0.3, 1.0),  # How active the user is
            'time_preference': random.choice(['morning', 'afternoon', 'evening', 'night'])
        }
        
        # Generate interactions
        articles_read = []
        
        for _ in range(int(interactions_per_user * user_preferences[user_id]['activity_level'])):
            # Time-based interaction generation
            if user_preferences[user_id]['time_preference'] == 'morning':
                hour = random.randint(6, 11)
            elif user_preferences[user_id]['time_preference'] == 'afternoon':
                hour = random.randint(12, 17)
            elif user_preferences[user_id]['time_preference'] == 'evening':
                hour = random.randint(18, 22)
            else:  # night
                hour = random.randint(23, 24) if random.random() < 0.5 else random.randint(0, 5)
            
            # Preferred category selection with higher probability
            if random.random() < 0.7:  # 70% chance to read from preferred categories
                category = random.choice(user_preferences[user_id]['categories'])
                # Filter articles by category
                category_articles = [
                    aid for aid, adata in article_data.items()
                    if adata['category'] == category
                ]
                if category_articles:
                    article_id = random.choice(category_articles)
                else:
                    article_id = random.randint(0, num_articles - 1)
            else:
                article_id = random.randint(0, num_articles - 1)
            
            # Add interaction with timestamp
            interaction_time = base_date + timedelta(
                days=random.randint(0, 29),
                hours=hour,
                minutes=random.randint(0, 59)
            )
            
            articles_read.append({
                'article_id': article_id,
                'timestamp': interaction_time,
                'interaction_type': random.choice(['view', 'like', 'share', 'comment']),
                'duration': random.randint(30, 300)  # seconds spent on article
            })
            
        # Sort interactions by timestamp
        articles_read.sort(key=lambda x: x['timestamp'])
        user_history[user_id] = articles_read
    
    return user_history, article_data, user_preferences

def prepare_data(user_history, article_data, num_articles):
    """Convert user history to training data with enhanced features"""
    user_vectors = []
    labels = []
    
    print("Preparing training data...")
    for user_id, interactions in user_history.items():
        # Create user interaction vector
        user_vector = np.zeros(num_articles)
        recency_weights = np.linspace(0.5, 1.0, len(interactions))  # More weight to recent interactions
        
        for interaction, weight in zip(interactions, recency_weights):
            article_id = interaction['article_id']
            interaction_weight = {
                'view': 1.0,
                'like': 2.0,
                'share': 3.0,
                'comment': 2.5
            }[interaction['interaction_type']]
            
            user_vector[article_id] += weight * interaction_weight
        
        # Normalize vector
        if np.sum(user_vector) > 0:
            user_vector = user_vector / np.sum(user_vector)
        
        user_vectors.append(user_vector)
        
        # Create label vector (1 for articles user might like)
        label = np.zeros(num_articles)
        for interaction in interactions[-5:]:  # Use last 5 interactions for testing
            label[interaction['article_id']] = 1
        labels.append(label)
    
    return np.array(user_vectors), np.array(labels)

def train_recommendation_system(num_users=1000, num_articles=10000, epochs=10):
    """Train the recommendation system with enhanced data"""
    print(f"Starting training with {num_users} users and {num_articles} articles...")
    
    # Generate enhanced synthetic data
    user_history, article_data, user_preferences = generate_synthetic_data(
        num_users=num_users,
        num_articles=num_articles
    )
    
    # Prepare training data
    user_vectors, labels = prepare_data(user_history, article_data, num_articles)
    
    # Initialize and train model
    model = RecommendationModel()
    
    # Training loop with progress tracking
    print("\nTraining progress:")
    total_users = len(user_vectors)
    for epoch in range(epochs):
        print(f"Epoch {epoch + 1}/{epochs}")
        for i, (user_vector, label) in enumerate(zip(user_vectors, labels)):
            if i % 100 == 0:
                print(f"Processing user {i}/{total_users}")
            model.update_user_profile(
                user_id=i,
                search_query="",  # No search query for synthetic data
                article_data={
                    'timestamp': datetime.now(),
                    'category': random.choice(list(article_data.values()))['category'],
                    'articles': [{'title': f'Article {j}', 'description': ''} 
                                for j in np.where(label == 1)[0]]
                }
            )
    
    return model

def test_recommendations(model, num_test_users=5):
    """Test the recommendation system with enhanced metrics"""
    print("\nTesting recommendations...")
    
    # Generate test articles
    test_articles = [
        {
            'title': f'Test Article {i}',
            'description': f'Description for article {i}',
            'category': random.choice(['technology', 'sports', 'politics', 'entertainment', 'business'])
        }
        for i in range(20)
    ]
    
    # Test for multiple users
    for i in range(num_test_users):
        print(f"\nTest User {i + 1}:")
        recommendations = model.get_recommendations(f"test_user_{i}", test_articles)
        
        print("Top 5 recommended articles:")
        for j, article in enumerate(recommendations[:5], 1):
            print(f"{j}. Category: {article['category']} - {article['title']}")

if __name__ == "__main__":
    # Configuration
    NUM_USERS = 1000
    NUM_ARTICLES = 10000
    EPOCHS = 5
    
    # Train model
    trained_model = train_recommendation_system(
        num_users=NUM_USERS,
        num_articles=NUM_ARTICLES,
        epochs=EPOCHS
    )
    
    # Test recommendations
    test_recommendations(trained_model)