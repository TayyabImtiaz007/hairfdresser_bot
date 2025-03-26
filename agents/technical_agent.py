from openai import OpenAI
import re
import time
import os


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TECHNICAL_AGENT_ID = "asst_ZsB2PzpoJYU98sqcSmwTG0er"  # Leave empty to create a new assistant

TECHNICAL_AGENT_PROMPT = """
You are a Technical Agent. Analyze an image uploaded in the message using the vector store of all adventure files.

Tasks:
1. Analyze: Provide a detailed breakdown of light conditions, hair length, symmetry, tools used, and specific cutting/styling techniques observed in the image.
2. Match: Identify the closest adventure (name, level, number) from the vector store, even if speculative, and explain why it matches based on observed features. If no exact match, suggest the most likely adventure.

Output:
- Analysis: 
  - Light conditions: "[Detailed description of lighting and its effect on visibility]."
  - Hair Length: "[Specific length, style notes, and any standout features]."
  - Symmetry: "[Detailed assessment of balance, shape, and consistency]."
  - Tools: "[List tools inferred from the image, with their likely use]."
  - Techniques: "[Specific cutting or styling methods observed, with notes on execution]."
- Adventure Match: "Matches Adventure [number] - [level] (or 'Likely Adventure [number] - [level]' if speculative). Reason: [Detailed explanation tying image features to the adventure file, e.g., techniques, style]."

Be detailed, concise, and always provide an adventure match (exact or speculative). Use file_search with the attached vector store.
"""

def get_technical_feedback(image_url, vector_store_id, content_stripped=""):
    global TECHNICAL_AGENT_ID
    
    if not TECHNICAL_AGENT_ID:
        print("No TECHNICAL_AGENT_ID provided. Creating a new assistant...")
        new_assistant = client.beta.assistants.create(
            name="Technical Agent",
            instructions=TECHNICAL_AGENT_PROMPT,
            tools=[{"type": "file_search"}],
            model="gpt-4o"
        )
        TECHNICAL_AGENT_ID = new_assistant.id
        print(f"New Technical Agent created with ID: {TECHNICAL_AGENT_ID}")
    else:
        print(f"Using existing Technical Agent with ID: {TECHNICAL_AGENT_ID}")

    assistant = client.beta.assistants.retrieve(TECHNICAL_AGENT_ID)
    
    if not vector_store_id:
        raise Exception("No vector_store_id provided. Cannot proceed without a vector store.")
    
    # Attach vector store if not already attached
    if not hasattr(assistant, "tool_resources") or not assistant.tool_resources.file_search or not assistant.tool_resources.file_search.vector_store_ids:
        print(f"Attaching vector store {vector_store_id} to assistant {TECHNICAL_AGENT_ID}...")
        assistant = client.beta.assistants.update(
            TECHNICAL_AGENT_ID,
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}}
        )
        print(f"Vector store {vector_store_id} attached to assistant.")

    thread = client.beta.threads.create()
    content = [{"type": "text", "text": f"Analyze this: {content_stripped}"}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=content
    )
    
    run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=TECHNICAL_AGENT_ID)
    
    timeout = 60
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise Exception(f"Assistant run timed out after {timeout} seconds.")
        
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        print(f"Run status: {run_status.status}")
        if run_status.status == "completed":
            break
        elif run_status.status in ["failed", "cancelled", "expired"]:
            error_msg = f"Assistant run failed with status: {run_status.status}"
            if hasattr(run_status, "last_error") and run_status.last_error:
                error_msg += f" - LastError(code='{run_status.last_error.code}', message='{run_status.last_error.message}')"
            raise Exception(error_msg)
        time.sleep(2)
    
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    feedback = messages.data[0].content[0].text.value
    adventure_number = re.search(r"Adventure (\d+)", feedback)
    adventure_number = int(adventure_match.group(1)) if (adventure_match := re.search(r"Adventure (\d+)", feedback)) else None
    
    return feedback, adventure_number