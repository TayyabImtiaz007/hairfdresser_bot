import requests
from auth import get_jwt_token  # Import the function to get the token

class BuddyBossClient:
    def __init__(self):
        self.base_url = "https://stg-my-hairdresser-508.ew1.rapydapps.cloud/"  # Correct base URL for BuddyBoss API
        self.token = get_jwt_token()  # Get the token dynamically
        if not self.token:
            raise Exception("Failed to obtain JWT token for BuddyBossClient.")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def get_user_info(self, user_id):
        """
        Fetch user information from BuddyBoss API.
        """
        url = f"{self.base_url}/members/{user_id}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch user info for user {user_id}: {e}")
            return None

    def post_comment(self, activity_id, comment_content):
        """
        Post a comment on a specific activity.
        """
        url = f"{self.base_url}/activity/{activity_id}/comment"
        payload = {
            "content": comment_content
        }
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to post comment on activity {activity_id}: {e}")
            return None
