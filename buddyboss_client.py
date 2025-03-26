import requests
import logging
from auth import token, generate_jwt_token

# Configure logging with the same format as main.py
logging.basicConfig(
    filename="agent_outputs.log",
    level=logging.INFO,
    format="%(asctime)s - Post ID: %(post_id)s - Agent: %(agent)s - %(message)s",
)

# Update the formatter to provide default values
logger = logging.getLogger()
for handler in logger.handlers:
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - Post ID: %(post_id)s - Agent: %(agent)s - %(message)s",
        defaults={"post_id": "N/A", "agent": "Unknown"}
    ))

class BuddyBossClient:
    def __init__(self, base_url="https://stg-my-hairdresser-508.ew1.rapydapps.cloud/"):
        self.base_url = base_url
        self.auth_header = {"Authorization": f"Bearer {token}"}
        self.logger = logging.getLogger(__name__)

    def _refresh_jwt_token(self):
        """Refresh the JWT token using the existing logic in auth.py"""
        try:
            new_token, _ = generate_jwt_token()
            self.auth_header = {"Authorization": f"Bearer {new_token}"}
            self.logger.info("JWT token refreshed successfully.", extra={"post_id": "N/A", "agent": "BuddyBossClient"})
        except Exception as e:
            self.logger.error(f"Failed to refresh JWT token: {str(e)}", extra={"post_id": "N/A", "agent": "BuddyBossClient"})
            raise

    def create_comment(self, post_id: int, comment_content: str) -> bool:
        """Post a comment on a BuddyBoss activity"""
        try:
            self.logger.info(f"Creating comment on post {post_id}...", extra={"post_id": post_id, "agent": "BuddyBossClient"})
            comment_url = f"{self.base_url}/wp-json/buddyboss/v1/activity/{post_id}/comment"
            payload = {"content": comment_content}
            response = requests.post(comment_url, headers=self.auth_header, json=payload, timeout=10)
            if response.status_code == 401:  # Unauthorized, token likely expired
                self.logger.warning("JWT token expired, refreshing...", extra={"post_id": post_id, "agent": "BuddyBossClient"})
                self._refresh_jwt_token()
                response = requests.post(comment_url, headers=self.auth_header, json=payload, timeout=10)
            response.raise_for_status()
            activity_url = f"{self.base_url}/activity/{post_id}/"
            self.logger.info(
                f"Comment created successfully. View it here: \033]8;;{activity_url}\033\\{activity_url}\033]8;;\033\\",
                extra={"post_id": post_id, "agent": "BuddyBossClient"}
            )
            return True
        except Exception as e:
            self.logger.error(f"Error creating comment: {str(e)}", extra={"post_id": post_id, "agent": "BuddyBossClient"})
            return False