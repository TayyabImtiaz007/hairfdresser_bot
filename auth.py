import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# BuddyBoss API credentials
BASE_URL = os.getenv("BUDDYBOSS_BASE_URL")
USERNAME = os.getenv("WP_USERNAME")
PASSWORD = os.getenv("WP_PASSWORD")

def get_jwt_token():
    """
    Authenticate with the BuddyBoss API and return a JWT token.
    Returns None if authentication fails.
    """
    print("🔑 Authenticating to get JWT token...")
    auth_url = f"{BASE_URL}/jwt-authorize"
    payload = {
        "username": USERNAME,
        "password": PASSWORD
    }
    try:
        response = requests.post(auth_url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if token:
            print("✓ JWT token obtained successfully!")
            return token
        else:
            print("❌ Failed to obtain JWT token: No token in response")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to obtain JWT token: {e}")
        return None

def verify_connection(current_token=None):
    """
    Verify connection to the BuddyBoss API.
    If current_token is not provided, it will attempt to fetch a new token.
    Returns True if the connection is successful, False otherwise.
    """
    # If no token is provided, fetch a new one
    if not current_token:
        current_token = get_jwt_token()
        if not current_token:
            return False

    # Use the token to verify the connection
    headers = {
        "Authorization": f"Bearer {current_token}"
    }
    test_url = f"{BASE_URL}/test-endpoint"  # Replace with an actual lightweight endpoint if available
    try:
        response = requests.get(test_url, headers=headers, timeout=5)
        response.raise_for_status()
        print("✓ Connection verified successfully!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection verification failed: {e}")
        return False
