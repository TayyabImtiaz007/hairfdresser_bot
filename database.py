import sqlite3
import json
from datetime import datetime, timezone

DATABASE = "hairdressing_history.db"

def create_connection():
    """Create a database connection to the SQLite database."""
    return sqlite3.connect(DATABASE)

def create_tables():
    """Create the necessary tables in the database if they don't exist."""
    conn = create_connection()
    cursor = conn.cursor()
    
    # Table for storing posts fetched from the website
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            name TEXT,
            bp_media_id TEXT,
            adventure_number TEXT,
            adventure_level TEXT,
            content_stripped TEXT,
            post_timestamp TEXT,
            activity_id INTEGER,
            processed INTEGER DEFAULT 0
        )
    ''')
    
    # Table for storing user history (processed post data)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT,
            adventure_name TEXT,
            image_urls TEXT,
            technical_analysis TEXT,
            knowledge_history TEXT,
            final_comment TEXT,
            rating INTEGER,
            post_date TEXT
        )
    ''')
    
    # Table for storing the last fetch timestamp
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fetch_timestamps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_fetch TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_last_fetch_time():
    """Fetch the last fetch timestamp from the database."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_fetch FROM fetch_timestamps ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "1970-01-01T00:00:00Z"

def get_latest_post_timestamp():
    """Fetch the most recent post_timestamp from the user_posts table."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT post_timestamp FROM user_posts ORDER BY post_timestamp DESC LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "1970-01-01T00:00:00Z"

def insert_post(user_id, name, bp_media_id, adventure_number, adventure_level, content_stripped, post_timestamp, activity_id):
    """Insert a new post into the user_posts table if it doesn't already exist."""
    conn = create_connection()
    cursor = conn.cursor()
    
    # Check if the post already exists based on activity_id
    cursor.execute("SELECT id FROM user_posts WHERE activity_id = ?", (activity_id,))
    if cursor.fetchone():
        conn.close()
        print(f"Skipping duplicate post with activity_id {activity_id}")
        return
    
    cursor.execute('''
        INSERT INTO user_posts (user_id, name, bp_media_id, adventure_number, adventure_level, content_stripped, post_timestamp, activity_id, processed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    ''', (user_id, name, json.dumps(bp_media_id), adventure_number, adventure_level, content_stripped, post_timestamp, activity_id))
    
    # Update the fetch timestamp
    cursor.execute("INSERT INTO fetch_timestamps (last_fetch) VALUES (?)", (datetime.now(timezone.utc).isoformat(),))
    
    conn.commit()
    conn.close()

# Other functions (get_unprocessed_posts, mark_post_processed, store_user_history, fetch_user_history) remain unchanged

def get_unprocessed_posts():
    """Retrieve all unprocessed posts from the user_posts table."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, name, bp_media_id, adventure_number, content_stripped, activity_id FROM user_posts WHERE processed = 0")
    rows = cursor.fetchall()
    conn.close()
    # Deserialize bp_media_id from JSON
    return [(row[0], row[1], row[2], json.loads(row[3]) if row[3] else [], row[4], row[5], row[6]) for row in rows]

def mark_post_processed(post_id):
    """Mark a post as processed in the user_posts table."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE user_posts SET processed = 1 WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

def store_user_history(post_id, user_id, content, adventure_name, image_urls, technical_analysis, knowledge_history, final_comment, rating, post_date):
    """Store the processed post data in the user_history table."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_history (post_id, user_id, content, adventure_name, image_urls, technical_analysis, knowledge_history, final_comment, rating, post_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (post_id, user_id, content, adventure_name, json.dumps(image_urls), technical_analysis, knowledge_history, final_comment, rating, post_date))
    conn.commit()
    conn.close()

def fetch_user_history(user_id):
    """Fetch the history of processed posts for a given user."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT post_id, content, adventure_name, image_urls, technical_analysis, knowledge_history, final_comment, rating, post_date FROM user_history WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    # Deserialize image_urls from JSON
    return [(row[0], row[1], row[2], json.loads(row[3]) if row[3] else [], row[4], row[5], row[6], row[7], row[8]) for row in rows]