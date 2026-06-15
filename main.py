import os
import base64
import json
import requests
from email.mime.text import MIMEText
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# NVIDIA API configurations
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Gmail API scopes (read-only, write/modify, and send permissions)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify"
]

TOKENS_DIR = "tokens"

def get_gmail_service():
    """Initializes and returns the Gmail service after user selection and authentication."""
    os.makedirs(TOKENS_DIR, exist_ok=True)
    
    # List existing accounts
    existing_accounts = [f[:-5] for f in os.listdir(TOKENS_DIR) if f.endswith(".json")]
    selected_email = None

    if existing_accounts:
        print("\nAvailable Gmail accounts:")
        for i, email in enumerate(existing_accounts, 1):
            print(f"[{i}] {email}")
        print(f"[{len(existing_accounts) + 1}] Login with a new account")
        
        choice = input(f"Select an account (1-{len(existing_accounts) + 1}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(existing_accounts):
                selected_email = existing_accounts[idx]
        except ValueError:
            pass

    creds = None
    token_path = None

    if selected_email:
        token_path = os.path.join(TOKENS_DIR, f"{selected_email}.json")
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Check if we have valid credentials; if not, or if scopes are insufficient, authenticate
    needs_auth = False
    if not creds or not creds.valid:
        needs_auth = True
    elif not all(scope in (creds.scopes or []) for scope in SCOPES):
        print("\n[Notice] Existing token has limited permissions. Re-authenticating to enable sending/drafting emails...")
        needs_auth = True

    if needs_auth:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                if token_path:
                    with open(token_path, "w") as token_file:
                        token_file.write(creds.to_json())
            except Exception:
                # If refresh fails, fall back to new authentication
                creds = None
        
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            
            # Fetch user email automatically to name the token file properly
            temp_service = build("gmail", "v1", credentials=creds)
            profile = temp_service.users().getProfile(userId="me").execute()
            user_email = profile.get("emailAddress", "unknown_user").lower()
            
            token_path = os.path.join(TOKENS_DIR, f"{user_email}.json")
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())
            print(f"Successfully authenticated and saved token for: {user_email}")

    return build("gmail", "v1", credentials=creds)

# --- Email Tool Helpers ---

def get_body_from_payload(payload):
    """Recursively extract the body text from the message payload."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            body += get_body_from_payload(part)
    else:
        mime_type = payload.get("mimeType", "")
        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                body += base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8", errors="ignore")
    return body

def list_emails(service, query=None, max_results=5):
    """Lists recent emails based on an optional search query."""
    try:
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get("messages", [])
        email_list = []
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", 
                id=msg["id"], 
                format="metadata", 
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()
            
            headers = detail.get("payload", {}).get("headers", [])
            subject = "No Subject"
            sender = "Unknown"
            date = "Unknown"
            for h in headers:
                if h["name"] == "Subject":
                    subject = h["value"]
                elif h["name"] == "From":
                    sender = h["value"]
                elif h["name"] == "Date":
                    date = h["value"]
                    
            email_list.append({
                "id": msg["id"],
                "from": sender,
                "subject": subject,
                "date": date,
                "snippet": detail.get("snippet", "")
            })
        return email_list
    except HttpError as error:
        return f"Error listing emails: {error}"

def get_email(service, email_id):
    """Fetches details and full body of a specific email by ID."""
    try:
        email = service.users().messages().get(userId="me", id=email_id).execute()
        headers = email.get("payload", {}).get("headers", [])
        subject = "No Subject"
        sender = "Unknown"
        date = "Unknown"
        for h in headers:
            if h["name"] == "Subject":
                subject = h["value"]
            elif h["name"] == "From":
                sender = h["value"]
            elif h["name"] == "Date":
                date = h["value"]
        
        body = get_body_from_payload(email.get("payload", {}))
        if not body:
            body = email.get("snippet", "")
            
        return {
            "id": email_id,
            "from": sender,
            "subject": subject,
            "date": date,
            "body": body.strip()
        }
    except HttpError as error:
        return f"Error fetching email details: {error}"

def send_email(service, to, subject, body):
    """Sends a new email directly."""
    try:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body_payload = {"raw": raw}
        
        sent_message = service.users().messages().send(userId="me", body=body_payload).execute()
        return f"Successfully sent email to {to} with Subject: '{subject}'. Message ID: {sent_message['id']}"
    except HttpError as error:
        return f"Failed to send email to {to}: {error}"

def create_draft(service, to, subject, body):
    """Creates a draft email."""
    try:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body_payload = {"message": {"raw": raw}}
        
        draft = service.users().drafts().create(userId="me", body=body_payload).execute()
        return f"Successfully created draft for {to} with Subject: '{subject}'. Draft ID: {draft['id']}"
    except HttpError as error:
        return f"Failed to create draft for {to}: {error}"

# --- LLM Integration ---

def call_nvidia_llm(messages):
    """Calls the NVIDIA Chat Completions API with the messages history."""
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY is not set. Please set it in your .env file.")
        
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "qwen/qwen3.5-122b-a10b",
        "messages": messages,
        "max_tokens": 768,
        "temperature": 0.1,  # Low temperature for highly reliable structure/JSON outputs
        "top_p": 0.95,
        "stream": False
    }
    
    try:
        response = requests.post(NVIDIA_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return json.dumps({
            "thought": f"An error occurred while calling the LLM API: {e}",
            "final_response": f"I hit an error communicating with the AI model: {e}"
        })

# --- Agent Core Loop ---

def run_agent_loop(service, user_prompt):
    """Executes the agent tool-execution loop based on the user's prompt."""
    system_instruction = """You are an elite AI Email Agent with direct access to the user's Gmail account and the ability to process emails using helper tools.

You have access to the following tools:
1. `list_emails(query=None, max_results=5)`
   - Lists recent emails. `query` supports Gmail search filters (e.g. 'is:unread', 'from:boss@company.com', 'subject:report').
2. `get_email(email_id)`
   - Fetches the full content and details of a specific email by its ID. ALWAYS use this if you need to read an email body before drafting a reply.
3. `send_email(to, subject, body)`
   - Sends an email to a recipient immediately.
4. `create_draft(to, subject, body)`
   - Creates a draft email that the user can review or send later.

You must interact with the orchestrator by responding with a single JSON object. Do not wrap the JSON object in markdown blocks (e.g. do not use ```json) and do not put any text before or after the JSON.

Choose one of the two formats below:

Format A: If you need to execute a tool:
{
  "thought": "Explain your step-by-step reasoning and why this tool call is necessary.",
  "action": "list_emails" or "get_email" or "send_email" or "create_draft",
  "action_input": {
    ... tool parameters here ...
  }
}

Format B: If you have finished the user's request and want to give a final response:
{
  "thought": "Explain why the task is complete.",
  "final_response": "Write your detailed reply to the user here."
}

Important Rules:
- If asked to reply/answer an email, first `list_emails` to locate it, call `get_email` to read the context, and then call `send_email` or `create_draft` to reply.
- Produce valid JSON ONLY.
"""

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_prompt}
    ]
    
    max_steps = 6
    for step in range(max_steps):
        print(f"\n[Agent Thinking - Step {step+1}]...")
        response_text = call_nvidia_llm(messages)
        
        # Clean markdown code blocks if any
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()
        
        try:
            response_data = json.loads(clean_text)
        except Exception as e:
            print(f"Failed to parse AI output as JSON: {e}")
            print(f"Raw Output: {response_text}")
            break
            
        thought = response_data.get("thought", "No thought provided.")
        print(f"\n> Agent Thought: {thought}")
        
        if "final_response" in response_data:
            print(f"\n[Agent Final Response]:\n{response_data['final_response']}\n")
            break
            
        action = response_data.get("action")
        action_input = response_data.get("action_input", {})
        
        if not action:
            print("Error: No action or final response provided by the agent.")
            break
            
        print(f"--> [Action]: Executing '{action}' with input: {action_input}")
        
        # Tool execution routing
        if action == "list_emails":
            result = list_emails(service, query=action_input.get("query"), max_results=action_input.get("max_results", 5))
        elif action == "get_email":
            result = get_email(service, action_input.get("email_id"))
        elif action == "send_email":
            result = send_email(service, action_input.get("to"), action_input.get("subject"), action_input.get("body"))
        elif action == "create_draft":
            result = create_draft(service, action_input.get("to"), action_input.get("subject"), action_input.get("body"))
        else:
            result = f"Error: Tool '{action}' is not supported."
            
        print(f"--> [Result]: {result}")
        
        # Feed the execution results back to the agent
        messages.append({"role": "assistant", "content": response_text})
        messages.append({"role": "user", "content": f"Tool execution result:\n{json.dumps(result)}"})
        
    else:
        print("\nReached max agent execution steps without producing a final response.")

# --- Interactive Main Loop ---

def main():
    print("=" * 60)
    print("           WELCOME TO AI EMAIL AGENT            ")
    print("=" * 60)
    
    try:
        service = get_gmail_service()
    except Exception as e:
        print(f"Error initializing Gmail connection: {e}")
        return
        
    print("\nGmail Agent authenticated successfully!")
    print("You can now prompt the agent to read, compose, draft, or send emails.")
    print("Type 'exit' or 'quit' to end the session.")
    print("=" * 60)
    
    while True:
        try:
            prompt = input("\nWhat would you like the agent to do? -> ").strip()
            if not prompt:
                continue
            if prompt.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
                
            run_agent_loop(service, prompt)
            
        except KeyboardInterrupt:
            print("\nExiting session...")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
