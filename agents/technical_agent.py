import asyncio
from openai import AsyncOpenAI
import re
import os

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TECHNICAL_AGENT_ID = "asst_ZsB2PzpoJYU98sqcSmwTG0er"

TECHNICAL_AGENT_PROMPT = """
You are a Technical Agent. Analyze an image uploaded in the message using the vector store of adventure files.
If the post mentions 'Advanced Cut' or 'Advanced', use the Advanced Cut Vector Store (ID: {ADVANCED_VECTOR_STORE_ID}).
Otherwise, use the Basic Cut Vector Store (ID: {BASIC_VECTOR_STORE_ID}).
The post may mention a specific adventure number (e.g., 'Abenteuer 11' or 'Adventure 11'). If an adventure number is mentioned, you must:
Identify the adventure number (e.g., '11' from 'Abenteuer 11').
Only use the file that matches that adventure number from the selected vector store. For the Basic Cut Vector Store, the file will be named 'Basic Cut Adventure X.docx' (e.g., 'Basic Cut Adventure 11.docx' for adventure 11). For the Advanced Cut Vector Store, the file will be named 'Advanced Cut Adventure X.docx' (e.g., 'Advanced Cut Adventure 11.docx' for adventure 11).
Do not include information from other adventure files unless the specific file for the mentioned adventure number is missing or does not contain the necessary information. If you must use information from other files or general knowledge, clearly state that the information is not specific to the mentioned adventure and explain why you are including it.
Provide detailed feedback based on the adventure files in the selected vector store, prioritizing the file that matches the adventure number mentioned in the post. If no adventure number is mentioned, you may use all relevant files from the vector store to provide a comprehensive response.
"""

async def get_technical_feedback(image_url, vector_store_id, content_stripped=""):
    global TECHNICAL_AGENT_ID
    
    if not TECHNICAL_AGENT_ID:
        print("No TECHNICAL_AGENT_ID provided. Creating a new assistant...")
        new_assistant = await client.beta.assistants.create(
            name="Technical Agent",
            instructions=TECHNICAL_AGENT_PROMPT,
            tools=[{"type": "file_search"}],
            model="gpt-4o"
        )
        TECHNICAL_AGENT_ID = new_assistant.id
        print(f"New Technical Agent created with ID: {TECHNICAL_AGENT_ID}")
    else:
        print(f"Using existing Technical Agent with ID: {TECHNICAL_AGENT_ID}")

    assistant = await client.beta.assistants.retrieve(TECHNICAL_AGENT_ID)
    
    if not vector_store_id:
        raise Exception("No vector_store_id provided. Cannot proceed without a vector store.")
    
    if not hasattr(assistant, "tool_resources") or not assistant.tool_resources.file_search or not assistant.tool_resources.file_search.vector_store_ids:
        print(f"Attaching vector store {vector_store_id} to assistant {TECHNICAL_AGENT_ID}...")
        assistant = await client.beta.assistants.update(
            TECHNICAL_AGENT_ID,
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}}
        )
        print(f"Vector store {vector_store_id} attached to assistant.")

    thread = await client.beta.threads.create()
    content = [{"type": "text", "text": f"Analyze this: {content_stripped}"}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    
    await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=content
    )
    
    # Use create_and_poll to avoid manual polling
    run = await client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=TECHNICAL_AGENT_ID,
        poll_interval_ms=1000  # Check every 1 second
    )
    
    if run.status != "completed":
        raise Exception(f"Assistant run failed with status: {run.status}")

    messages = await client.beta.threads.messages.list(thread_id=thread.id)
    feedback = messages.data[0].content[0].text.value
    adventure_number = int(adventure_match.group(1)) if (adventure_match := re.search(r"Adventure (\d+)", feedback)) else None
    
    return feedback, adventure_number
