from openai import OpenAI
from database import fetch_user_history
import time
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
KNOWLEDGE_HISTORIK_AGENT_ID = "asst_YrshuDTagBGcf8JqdoRq1Ywk"

KNOWLEDGE_HISTORIK_PROMPT = """
You are a Wissens-Historik Agent. Analyze the user's historical data to provide insights on their progress.

Tasks:
1. Review the user's past submissions (content, adventure names, technical analysis, final comments).
2. Identify patterns, improvements, or recurring issues.
3. Provide a concise summary of the user's progress.

Output:
- Summary: "The user has completed [X] adventures, showing [improvement/consistent issues] in [specific areas]. Recent submissions indicate [specific observations]."

If no historical data is available, return:
- Summary: "No historical data available for this user."
"""

def get_historical_feedback(user_id, vector_store_id):
    global KNOWLEDGE_HISTORIK_AGENT_ID
    
    if not KNOWLEDGE_HISTORIK_AGENT_ID:
        print("No KNOWLEDGE_HISTORIK_AGENT_ID provided. Creating a new assistant...")
        new_assistant = client.beta.assistants.create(
            name="Wissens-Historik Agent",
            instructions=KNOWLEDGE_HISTORIK_PROMPT,
            tools=[{"type": "file_search"}],
            model="gpt-4o"
        )
        KNOWLEDGE_HISTORIK_AGENT_ID = new_assistant.id
        print(f"New Wissens-Historik Agent created with ID: {KNOWLEDGE_HISTORIK_AGENT_ID}")

    assistant = client.beta.assistants.retrieve(KNOWLEDGE_HISTORIK_AGENT_ID)
    
    if not vector_store_id:
        raise Exception("No vector_store_id provided. Cannot proceed without a vector store.")
    
    if not hasattr(assistant, "tool_resources") or not assistant.tool_resources.file_search or not assistant.tool_resources.file_search.vector_store_ids:
        print(f"Attaching vector store {vector_store_id} to assistant {KNOWLEDGE_HISTORIK_AGENT_ID}...")
        assistant = client.beta.assistants.update(
            KNOWLEDGE_HISTORIK_AGENT_ID,
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}}
        )
        print(f"Vector store {vector_store_id} attached to assistant.")

    # Fetch user history
    history = fetch_user_history(user_id)
    if not history:
        return "No historical data available for this user."

    # Format history for the assistant
    history_text = "User History:\n"
    for entry in history:
        post_id, content, adventure_name, image_urls, technical_analysis, knowledge_history, final_comment, rating, post_date = entry
        history_text += f"- Post ID: {post_id}, Adventure: {adventure_name}, Content: {content}, Technical Analysis: {technical_analysis}, Final Comment: {final_comment}, Date: {post_date}\n"

    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=[{"type": "text", "text": f"Analyze the following user history:\n{history_text}"}]
    )
    
    run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=KNOWLEDGE_HISTORIK_AGENT_ID)
    timeout = 60
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise Exception(f"Assistant run timed out after {timeout} seconds.")
        
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        print(f"Run status (Historical Agent): {run_status.status}")
        if run_status.status == "completed":
            break
        elif run_status.status in ["failed", "cancelled", "expired"]:
            raise Exception(f"Assistant run failed with status: {run_status.status}")
        time.sleep(2)
    
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    feedback = messages.data[0].content[0].text.value
    return feedback