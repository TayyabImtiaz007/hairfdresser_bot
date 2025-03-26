from openai import OpenAI
import time  # Explicit import
import os


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
META_AGENT_ID = "asst_mIB7i3swLSMEZCg0G4FnMYGt"

META_AGENT_PROMPT = """
You are a Meta Agent. Your role is to combine technical and historical feedback to provide a detailed, constructive, and encouraging final comment for the user, focusing on their hairdressing performance.

Tasks:
1. Review the Technical Feedback: Identify key strengths (e.g., symmetry, tool usage, styling techniques) and any areas for improvement (e.g., deviations, visibility issues).
2. Review the Historical Feedback: Understand the user's progress, patterns, and recurring themes (e.g., consistent improvement in precision, challenges with certain techniques).
3. Provide a Detailed Final Comment:
   - Highlight 2-3 specific strengths from the Technical Feedback, mentioning details like the haircut style, techniques, or tools used.
   - Connect the Historical Feedback to the current performance, explaining how past improvements or challenges have influenced this result.
   - Offer 1-2 pieces of actionable advice for improvement, tailored to the user’s current level and historical progress (e.g., refining a specific technique, experimenting with new tools, or addressing recurring issues).
   - Use an encouraging tone to motivate the user to continue improving.
"""

def get_final_comment(technical_feedback, historical_feedback):
    global META_AGENT_ID
    
    if not META_AGENT_ID:
        print("No META_AGENT_ID provided. Creating a new assistant...")
        new_assistant = client.beta.assistants.create(
            name="Meta Agent",
            instructions=META_AGENT_PROMPT,
            model="gpt-4o"
        )
        META_AGENT_ID = new_assistant.id
        print(f"New Meta Agent created with ID: {META_AGENT_ID}")

    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=[{"type": "text", "text": f"Technical Feedback: {technical_feedback}\nHistorical Feedback: {historical_feedback}"}]
    )
    
    run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=META_AGENT_ID)
    timeout = 60
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise Exception(f"Assistant run timed out after {timeout} seconds.")
        
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        print(f"Run status (Meta Agent): {run_status.status}")
        if run_status.status == "completed":
            break
        elif run_status.status in ["failed", "cancelled", "expired"]:
            raise Exception(f"Assistant run failed with status: {run_status.status}")
        time.sleep(2)  # Should now work with explicit import
    
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    feedback = messages.data[0].content[0].text.value
    return feedback