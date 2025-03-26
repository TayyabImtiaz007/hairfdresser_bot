import os
import time
import requests
import logging
import asyncio
import json
from datetime import datetime, timezone
from auth import verify_connection
from database import create_tables, mark_post_processed, get_unprocessed_posts, insert_post, get_last_fetch_time, get_latest_post_timestamp, store_user_history, fetch_user_history
from fetch_posts import fetch_posts_from_website
from agents.technical_agent import get_technical_feedback
from agents.wissens_historik_agent import get_historical_feedback
from agents.meta_agent import get_final_comment
from buddyboss_client import BuddyBossClient
from openai import OpenAI
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Load environment variables from .env file
load_dotenv()

# Logging setup
logging.basicConfig(
    filename="agent_outputs.log",
    level=logging.INFO,
    format="%(asctime)s - Post ID: %(post_id)s - Agent: %(agent)s - %(message)s",
)
logger = logging.getLogger()
for handler in logger.handlers:
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - Post ID: %(post_id)s - Agent: %(agent)s - %(message)s",
        defaults={"post_id": "N/A", "agent": "Unknown"}
    ))

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Vector Store IDs
ADVANCED_VECTOR_STORE_ID = os.getenv("ADVANCED_VECTOR_STORE_ID")
BASIC_VECTOR_STORE_ID = os.getenv("BASIC_VECTOR_STORE_ID")
REFERENCE_FILES_DIR = os.getenv("REFERENCE_FILES_DIR")

# Agent IDs
TECHNICAL_AGENT_ID = os.getenv("TECHNICAL_AGENT_ID")
KNOWLEDGE_HISTORIK_AGENT_ID = os.getenv("KNOWLEDGE_HISTORIK_AGENT_ID")
META_AGENT_ID = os.getenv("META_AGENT_ID")

# Global prompts
TECHNICAL_AGENT_PROMPT = """
You are a Technical Agent. Analyze an image uploaded in the message using the vector store of adventure files.
If the post mentions 'Advanced Cut' or 'Advanced', use the Advanced Cut Vector Store (ID: {ADVANCED_VECTOR_STORE_ID}).
Otherwise, use the Basic Cut Vector Store (ID: {BASIC_VECTOR_STORE_ID}).
Provide detailed feedback based on the adventure files in the selected vector store.
"""
KNOWLEDGE_HISTORIK_PROMPT = """
You are a Wissens-Historik Agent. Analyze the user's historical data...
"""
META_AGENT_PROMPT = """
You are a Meta Agent. Your role is to combine technical and historical feedback...
"""

# WebSocket clients
connected_clients = set()

# FastAPI app
app = FastAPI()

# Mount the static directory at /static
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# Serve index.html at the root path (/)
@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Declare global variables at the start of the function
    global TECHNICAL_AGENT_PROMPT, KNOWLEDGE_HISTORIK_PROMPT, META_AGENT_PROMPT

    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            if data['type'] == 'initial_data':
                history = fetch_user_history(311)
                if history:
                    post_id, content, adventure_name, image_urls, technical_analysis, knowledge_history, final_comment, rating, post_date = history[-1]
                    response = {
                        "user_id": "311",
                        "user_name": "Dilaur",
                        "adventure_number": adventure_name.split()[-1],
                        "image_urls": image_urls if image_urls else [],
                        "technical_input": content,
                        "technical_feedback": technical_analysis,
                        "technical_prompt": TECHNICAL_AGENT_PROMPT,
                        "historical_input": f"User ID: 311",
                        "historical_feedback": knowledge_history,
                        "historical_prompt": KNOWLEDGE_HISTORIK_PROMPT,
                        "meta_input": f"Technical Feedback: {technical_analysis}\nHistorical Feedback: {knowledge_history}",
                        "meta_feedback": final_comment,
                        "meta_prompt": META_AGENT_PROMPT
                    }
                    await websocket.send_json(response)
            elif data['type'] == 'update_prompt':
                agent = data['agent']
                new_prompt = data['prompt']
                try:
                    if agent == 'technical':
                        TECHNICAL_AGENT_PROMPT = new_prompt
                        client.beta.assistants.update(assistant_id=TECHNICAL_AGENT_ID, instructions=new_prompt)
                    elif agent == 'historical':
                        KNOWLEDGE_HISTORIK_PROMPT = new_prompt
                        client.beta.assistants.update(assistant_id=KNOWLEDGE_HISTORIK_AGENT_ID, instructions=new_prompt)
                    elif agent == 'meta':
                        META_AGENT_PROMPT = new_prompt
                        client.beta.assistants.update(assistant_id=META_AGENT_ID, instructions=new_prompt)
                    print(f"Updated {agent} prompt: {new_prompt}")
                except Exception as e:
                    print(f"Error updating prompt for {agent}: {e}")
                    await websocket.send_json({"error": f"Failed to update prompt for {agent}: {str(e)}"})
            elif data['type'] == 'process_next_post':
                unprocessed_posts = get_unprocessed_posts()
                if unprocessed_posts:
                    await process_post(unprocessed_posts[0], BuddyBossClient())
                else:
                    await send_update_to_clients({"message": "No unprocessed posts available."})
            elif data['type'] == 'get_vector_store_files':
                try:
                    advanced_files = client.vector_stores.files.list(vector_store_id=ADVANCED_VECTOR_STORE_ID)
                    basic_files = client.vector_stores.files.list(vector_store_id=BASIC_VECTOR_STORE_ID)
                    advanced_file_list = [{"id": file.id, "name": client.files.retrieve(file_id=file.id).filename} for file in advanced_files.data]
                    basic_file_list = [{"id": file.id, "name": client.files.retrieve(file_id=file.id).filename} for file in basic_files.data]
                    await send_update_to_clients({
                        "advanced_vector_store_files": advanced_file_list,
                        "basic_vector_store_files": basic_file_list
                    })
                except Exception as e:
                    print(f"Error fetching vector store files: {e}")
                    await websocket.send_json({"error": f"Failed to fetch vector store files: {str(e)}"})
            elif data['type'] == 'delete_vector_store_file':
                file_id = data['file_id']
                vector_store_type = data['vector_store_type']
                vector_store_id = ADVANCED_VECTOR_STORE_ID if vector_store_type == 'advanced' else BASIC_VECTOR_STORE_ID
                try:
                    client.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
                    print(f"Deleted file {file_id} from vector store {vector_store_id}")
                    advanced_files = client.vector_stores.files.list(vector_store_id=ADVANCED_VECTOR_STORE_ID)
                    basic_files = client.vector_stores.files.list(vector_store_id=BASIC_VECTOR_STORE_ID)
                    advanced_file_list = [{"id": file.id, "name": client.files.retrieve(file_id=file.id).filename} for file in advanced_files.data]
                    basic_file_list = [{"id": file.id, "name": client.files.retrieve(file_id=file.id).filename} for file in basic_files.data]
                    await send_update_to_clients({
                        "advanced_vector_store_files": advanced_file_list,
                        "basic_vector_store_files": basic_file_list
                    })
                except Exception as e:
                    print(f"Error deleting vector store file {file_id}: {e}")
                    await websocket.send_json({"error": f"Failed to delete vector store file: {str(e)}"})
            elif data['type'] == 'upload_file':
                file_content = data['file_content']
                file_name = data['file_name']
                vector_store_type = data['vector_store_type']
                vector_store_id = ADVANCED_VECTOR_STORE_ID if vector_store_type == 'advanced' else BASIC_VECTOR_STORE_ID
                try:
                    with open(file_name, "wb") as f:
                        f.write(bytes.fromhex(file_content))
                    file_obj = client.files.create(file=open(file_name, "rb"), purpose="assistants")
                    client.vector_stores.files.create(vector_store_id=vector_store_id, file_id=file_obj.id)
                    os.remove(file_name)
                    print(f"Uploaded {file_name} to vector store {vector_store_id}")
                    advanced_files = client.vector_stores.files.list(vector_store_id=ADVANCED_VECTOR_STORE_ID)
                    basic_files = client.vector_stores.files.list(vector_store_id=BASIC_VECTOR_STORE_ID)
                    advanced_file_list = [{"id": file.id, "name": client.files.retrieve(file_id=file.id).filename} for file in advanced_files.data]
                    basic_file_list = [{"id": file.id, "name": client.files.retrieve(file_id=file.id).filename} for file in basic_files.data]
                    await send_update_to_clients({
                        "advanced_vector_store_files": advanced_file_list,
                        "basic_vector_store_files": basic_file_list
                    })
                except Exception as e:
                    print(f"Error uploading file {file_name} to vector store: {e}")
                    await websocket.send_json({"error": f"Failed to upload file: {str(e)}"})
    except Exception as e:
        print(f"WebSocket connection closed: {e}")
    finally:
        connected_clients.remove(websocket)

async def send_update_to_clients(post_data):
    if connected_clients:
        for websocket in connected_clients.copy():
            try:
                await websocket.send_json(post_data)
            except Exception:
                connected_clients.remove(websocket)

async def process_post(post, buddyboss_client):
    post_id, user_id, user_name, bp_media_id, adventure_number, content_stripped, activity_id = post
    log_extra = {"post_id": post_id, "agent": ""}

    print(f"Starting processing for Post ID {post_id}...")
    try:
        image_urls = []
        if isinstance(bp_media_id, list):
            for media in bp_media_id:
                if "attachment_data" in media and isinstance(media["attachment_data"], dict):
                    attachment_data = media["attachment_data"]
                    if "media_theatre_popup" in attachment_data and isinstance(attachment_data["media_theatre_popup"], str) and attachment_data["media_theatre_popup"].startswith("http"):
                        image_urls.append(attachment_data["media_theatre_popup"])
                        continue
                if "url" in media and isinstance(media["url"], str) and media["url"].startswith("http"):
                    image_urls.append(media["url"])
                else:
                    logging.warning(f"Invalid or missing URL in bp_media_id for Post ID {post_id}: {media}", extra=log_extra)
        else:
            if bp_media_id and isinstance(bp_media_id, str) and bp_media_id.startswith("http"):
                image_urls = [bp_media_id]
            else:
                print(f"Skipping image analysis for Post ID {post_id}: No valid image URL.")
                logging.info(f"Skipping image analysis due to invalid or missing image URL: {bp_media_id}", extra={**log_extra, "agent": "Process"})

        content_lower = (content_stripped or "").lower()
        adventure_lower = (adventure_number or "").lower()
        is_advanced = "advanced cut" in content_lower or "advanced" in content_lower or "advanced cut" in adventure_lower or "advanced" in adventure_lower

        vector_store_id = ADVANCED_VECTOR_STORE_ID if is_advanced else BASIC_VECTOR_STORE_ID
        vector_store_used = "Advanced Cut" if is_advanced else "Basic Cut"
        print(f"Using vector store: {vector_store_used} (ID: {vector_store_id})")

        print(f"Calling Technical Agent for Post ID {post_id}...")
        technical_feedback, detected_adventure_number = get_technical_feedback(image_urls[0] if image_urls else None, vector_store_id, content_stripped)
        logging.info(f"Technical Feedback: {technical_feedback}", extra={**log_extra, "agent": "Technical Agent"})
        print(f"Technical Agent completed for Post ID {post_id}")

        print(f"Calling Historical Agent for Post ID {post_id}...")
        historical_feedback = get_historical_feedback(user_id, vector_store_id)
        logging.info(f"Historical Feedback: {historical_feedback}", extra={**log_extra, "agent": "Wissens-Historik Agent"})
        print(f"Historical Agent completed for Post ID {post_id}")

        print(f"Calling Meta Agent for Post ID {post_id}...")
        final_comment = get_final_comment(technical_feedback, historical_feedback)
        logging.info(f"Final Comment: {final_comment}", extra={**log_extra, "agent": "Meta Agent"})
        print(f"Meta Agent completed for Post ID {post_id}")

        print(f"Storing results for Post ID {post_id}...")
        store_user_history(
            post_id=post_id,
            user_id=user_id,
            content=content_stripped,
            adventure_name=f"Adventure {adventure_number or detected_adventure_number or 'Unknown'}",
            image_urls=image_urls,
            technical_analysis=technical_feedback,
            knowledge_history=historical_feedback,
            final_comment=final_comment,
            rating=4,
            post_date=datetime.now(timezone.utc).isoformat()
        )

        post_data = {
            "user_id": str(user_id),
            "user_name": user_name,
            "adventure_number": str(adventure_number or detected_adventure_number or "Unknown"),
            "image_urls": image_urls,
            "vector_store_used": vector_store_used,
            "technical_input": content_stripped,
            "technical_feedback": technical_feedback,
            "technical_prompt": TECHNICAL_AGENT_PROMPT,
            "historical_input": f"User ID: {user_id}",
            "historical_feedback": historical_feedback,
            "historical_prompt": KNOWLEDGE_HISTORIK_PROMPT,
            "meta_input": f"Technical Feedback: {technical_feedback}\nHistorical Feedback: {historical_feedback}",
            "meta_feedback": final_comment,
            "meta_prompt": META_AGENT_PROMPT
        }

        print(f"\n=== Final Response for Post {post_id} ===")
        print(f"User ID: {user_id}")
        print(f"User Name: {user_name}")
        print(f"Adventure Number: {adventure_number or detected_adventure_number or 'Unknown'}")
        print(f"Image URLs: {image_urls}")
        print(f"Vector Store Used: {vector_store_used}")
        print(f"Technical Feedback: {technical_feedback}")
        print(f"Historical Feedback: {historical_feedback}")
        print(f"Final Comment: {final_comment}")
        print("=====================================\n")

        await send_update_to_clients(post_data)
        mark_post_processed(post_id)
    except Exception as e:
        print(f"Error processing Post ID {post_id}: {e}")
        logging.error(f"Error processing post: {e}", extra={**log_extra, "agent": "Process"})
        await send_update_to_clients({"error": f"Failed to process post: {str(e)}"})

async def main(debug_mode=False):
    create_tables()
    # Verify connection without passing a token (handled internally by verify_connection)
    if not verify_connection():
        print("Connection to BuddyBoss API failed. Retrying in 60 seconds...")
        await asyncio.sleep(60)
        if not verify_connection():
            raise Exception("Connection failed after retry.")

    buddyboss_client = BuddyBossClient()

    print("Fetching all posts on first run...")
    try:
        posts = fetch_posts_from_website()
        logging.info(f"Fetched {len(posts)} posts: {posts}")
        print(f"Fetched {len(posts)} posts.")
        for post in posts:
            insert_post(
                user_id=post["user_id"],
                name=post.get("name", f"User_{post['user_id']}"),
                bp_media_id=post["bp_media_id"],
                adventure_number=post["adventure_number"],
                adventure_level=post["adventure_level"],
                content_stripped=post["content_stripped"],
                post_timestamp=post["timestamp"],
                activity_id=post["activity_id"]
            )
    except Exception as e:
        logging.error(f"Failed to fetch posts: {e}")
        print(f"Failed to fetch posts: {e}")

    fetch_interval = int(os.getenv("FETCH_INTERVAL_SECONDS"))
    last_fetch = datetime.now()

    while True:
        if (datetime.now() - last_fetch).total_seconds() >= fetch_interval:
            last_timestamp = get_latest_post_timestamp()
            print(f"Fetching new posts since {last_timestamp}...")
            try:
                new_posts = fetch_posts_from_website(last_timestamp)
                logging.info(f"Fetched {len(new_posts)} new posts: {new_posts}")
                print(f"Fetched {len(new_posts)} new posts.")
                for post in new_posts:
                    insert_post(
                        user_id=post["user_id"],
                        name=post.get("name", f"User_{post['user_id']}"),
                        bp_media_id=post["bp_media_id"],
                        adventure_number=post["adventure_number"],
                        adventure_level=post["adventure_level"],
                        content_stripped=post["content_stripped"],
                        post_timestamp=post["timestamp"],
                        activity_id=post["activity_id"]
                    )
                last_fetch = datetime.now()
            except Exception as e:
                logging.error(f"Failed to fetch new posts: {e}")
                print(f"Failed to fetch new posts: {e}")
        await asyncio.sleep(3600)

# Entry point to run both the main coroutine and the FastAPI app
if __name__ == "__main__":
    async def run_app_and_main():
        # Start the main loop as a task
        main_task = asyncio.create_task(main(debug_mode=True))
        # Start the FastAPI app
        config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)), loop="asyncio")
        server = uvicorn.Server(config)
        app_task = asyncio.create_task(server.serve())
        # Wait for both tasks to complete (they won't, as they run indefinitely)
        await asyncio.gather(main_task, app_task)

    asyncio.run(run_app_and_main())
