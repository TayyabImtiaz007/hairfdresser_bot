import requests

BASE_URL = "https://stg-my-hairdresser-508.ew1.rapydapps.cloud/"  # Updated to match the target server
WP_USERNAME = "Hairdressing.school Mentor"  # Replace with your WordPress username
WP_PASSWORD = "wyCs ESkt qkpT tzrh hsUJ uL6G"  # Replace with your WordPress password

token = None
token_expiry = 0

def generate_jwt_token():
    global token, token_expiry
    auth_url = f"{BASE_URL}/wp-json/jwt-auth/v1/token"
    payload = {"username": WP_USERNAME, "password": WP_PASSWORD}
    try:
        print("🔑 Authenticating to get JWT token...")
        response = requests.post(auth_url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if not token:
            raise ValueError("No token received from JWT authentication")
        token_expiry = 3600  # Token expiry is typically 1 hour (3600 seconds)
        print("✓ JWT token obtained successfully!")
        return token, token_expiry
    except requests.RequestException as e:
        print(f"❌ Error getting JWT token: {e}")
        raise

def verify_connection(current_token):
    try:
        headers = {"Authorization": f"Bearer {current_token}"}
        response = requests.get(f"{BASE_URL}/wp-json/buddyboss/v1/activity", headers=headers, timeout=10)
        response.raise_for_status()
        print(f"Connected to website successfully with JWT token.")
        return True
    except requests.RequestException as e:
        print(f"Error connecting to website: {e}")
        return False

# Generate token on import
token, token_expiry = generate_jwt_token()