import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# BuddyBoss API credentials
BASE_URL = os.getenv("BUDDYBOSS_BASE_URL", "https://stg-my-hairdresser-508.ew1.rapydapps.cloud")  # Root domain, without /wp-json
USERNAME = os.getenv("WP_USERNAME", "Hairdressing.school Mentor")
PASSWORD = os.getenv("WP_PASSWORD", "wyCs ESkt qkpT tzrh hsUJ uL6G")

# Global variables for token and expiry
token = None
token_expiry = 0

def get_jwt_token():
    """
    Authenticate with the BuddyBoss API and return a JWT token.
    Updates the global token and token_expiry variables.
    Returns the token if successful, raises an exception if it fails.
    """
    global token, token_expiry
    print("🔑 Authenticating to get JWT token...")
    auth_url = f"{BASE_URL}/wp-json/jwt-auth/v1/token"  # Correct endpoint for JWT authentication
    payload = {
        "username": USERNAME,
        "password": PASSWORD
    }
    try:
        response = requests.post(auth_url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if not token:
            raise ValueError("No token received from JWT authentication")
        token_expiry = 3600  # Token expiry is typically 1 hour (3600 seconds)
        print("✓ JWT token obtained successfully!")
        return token
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to obtain JWT token: {e}")
        raise

def verify_connection(current_token=None):
    """
    Verify connection to the BuddyBoss API.
    If current_token is not provided, it will attempt to fetch a new token.
    Returns True if the connection is successful, False otherwise.
    """
    global token, token_expiry
    # If no token is provided or the token has expired, fetch a new one
    if not current_token or token_expiry <= 0:
        try:
            current_token = get_jwt_token()
        except requests.exceptions.RequestException:
            return False

    # Use the token to verify the connection
    headers = {
        "Authorization": f"Bearer {current_token}"
    }
    test_url = f"{BASE_URL}/wp-json/buddyboss/v1/activity"  # Use a real endpoint to verify connectivity
    try:
        response = requests.get(test_url, headers=headers, timeout=5)
        response.raise_for_status()
        print("✓ Connection verified successfully!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection verification failed: {e}")
        return False

# Generate token on import
try:
    token = get_jwt_token()
except requests.exceptions.RequestException as e:
    print(f"Failed to initialize JWT token on import: {e}")
