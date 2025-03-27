import requests
import re
from auth import get_jwt_token  # Import the function to get the token

BASE_URL = "https://my.hairdressing.school/wp-json/buddyboss/v1/activity"  # Correct base URL for activity endpoint

def fetch_posts_from_website(last_timestamp=None):
    """
    Fetch posts from the BuddyBoss API that are newer than the given timestamp.
    If last_timestamp is None, fetch all posts with pagination.
    
    Args:
        last_timestamp (str): The latest post_timestamp from the database in ISO 8601 format.
                             If None, fetches all posts.
    
    Returns:
        list: A list of formatted post dictionaries.
    """
    # Get the JWT token dynamically
    try:
        token = get_jwt_token()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to obtain JWT token for API authentication: {e}")

    headers = {"Authorization": f"Bearer {token}"}
    params = {"per_page": 100}  # Maximum per page allowed by BuddyBoss API
    if last_timestamp:
        params["after"] = last_timestamp  # Filter posts after the given timestamp

    all_posts = []
    page = 1

    while True:
        params["page"] = page
        try:
            response = requests.get(BASE_URL, headers=headers, params=params, timeout=10)
            response.raise_for_status()  # Raises an exception for 4xx/5xx status codes
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch posts on page {page}: {str(e)}")

        posts = response.json()
        if not posts:  # If no more posts are returned, break the loop
            break

        formatted_posts = []
        for post in posts:
            # Extract post timestamp and skip if older than last_timestamp (fallback check)
            post_timestamp = post.get("date", "")
            if last_timestamp and post_timestamp and post_timestamp <= last_timestamp:
                print(f"Skipping post with timestamp {post_timestamp} (older than {last_timestamp})")
                continue

            activity_id = post.get("id", 0)
            user_id = post.get("user_id", 0)
            content_dict = post.get("content", {})
            content_stripped = post.get("content_stripped", content_dict.get("rendered", "") if isinstance(content_dict, dict) else str(content_dict))
            
            if not isinstance(content_stripped, str):
                content_stripped = ""
            
            # Use bp_media_ids for the image URL if available
            bp_media_id = ""
            if "bp_media_ids" in post and post["bp_media_ids"] and isinstance(post["bp_media_ids"], list) and len(post["bp_media_ids"]) > 0:
                bp_media_id = post["bp_media_ids"][0]["attachment_data"]["full"]
            
            adventure_match = re.search(r"Abenteuer (\d+)", content_stripped)
            level_match = re.search(r"(Basic Cut|Advanced Cut)", content_stripped)
            adventure_number = int(adventure_match.group(1)) if adventure_match else None
            adventure_level = level_match.group(1) if level_match else "Unknown"

            formatted_posts.append({
                "activity_id": activity_id,
                "user_id": user_id,
                "name": post.get("name"),
                "bp_media_id": post.get("bp_media_ids", []),
                "adventure_number": adventure_number,
                "adventure_level": adventure_level,
                "content_stripped": content_stripped,
                "timestamp": post_timestamp
            })
        
        all_posts.extend(formatted_posts)
        page += 1

    # Sort posts by timestamp to ensure chronological order
    all_posts.sort(key=lambda x: x["timestamp"])
    return all_posts
