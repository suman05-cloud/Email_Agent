import os
import base64
import json
import requests
from email.mime.text import MIMEText
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Email Agent API", version="1.0.0")

# Enable CORS for React frontend running on localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Configurations
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
CLIENT_SECRETS_FILE = "credentials.json"
TOKENS_DIR = "tokens"

# Gmail scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify"
]

# --- OAuth Endpoints ---

@app.get("/api/auth/url")
def get_auth_url():
    """Generates Google OAuth URL for frontend authentication redirection."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(status_code=500, detail="credentials.json file is missing on the server.")
        
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri="http://localhost:8000/api/auth/callback"
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return {"url": authorization_url}

@app.get("/api/auth/callback")
def auth_callback(code: str, state: Optional[str] = None):
    """Callback receiver that exchanges OAuth code for credentials token and redirects back to React."""
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri="http://localhost:8000/api/auth/callback"
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Determine email address
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", "unknown").lower()
        
        # Save token file under tokens/{email}.json
        os.makedirs(TOKENS_DIR, exist_ok=True)
        token_path = os.path.join(TOKENS_DIR, f"{email}.json")
        with open(token_path, "w") as f:
            f.write(creds.to_json())
            
        # Redirect user back to Vite frontend
        return RedirectResponse(url=f"http://localhost:5173/?email={email}")
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:5173/?error={str(e)}")

# --- Accounts & Status Endpoints ---

@app.get("/api/accounts")
def list_accounts():
    """Returns a list of all currently connected Gmail accounts (profiles with tokens)."""
    if not os.path.exists(TOKENS_DIR):
        return []
    accounts = [f[:-5] for f in os.listdir(TOKENS_DIR) if f.endswith(".json")]
    return accounts

@app.delete("/api/accounts/{email}")
def disconnect_account(email: str):
    """Disconnects a Gmail account by deleting its token file."""
    token_path = os.path.join(TOKENS_DIR, f"{email.lower()}.json")
    if os.path.exists(token_path):
        os.remove(token_path)
        return {"status": "success", "message": f"Successfully disconnected {email}"}
    raise HTTPException(status_code=404, detail=f"Account {email} not found.")

# --- Email API Core Helper Tools ---

def get_body_from_payload(payload):
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

def get_credentials(email: str) -> Credentials:
    token_path = os.path.join(TOKENS_DIR, f"{email.lower()}.json")
    if not os.path.exists(token_path):
        raise HTTPException(status_code=401, detail=f"No active credentials found for {email}. Please log in first.")
        
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        else:
            raise HTTPException(status_code=401, detail=f"Credentials for {email} are invalid or expired. Re-auth required.")
    return creds

def run_list_emails(service, query=None, max_results=5):
    try:
        results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = results.get("messages", [])
        email_list = []
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata", metadataHeaders=["Subject", "From", "Date"]
            ).execute()
            headers = detail.get("payload", {}).get("headers", [])
            subject, sender, date = "No Subject", "Unknown", "Unknown"
            for h in headers:
                if h["name"] == "Subject": subject = h["value"]
                elif h["name"] == "From": sender = h["value"]
                elif h["name"] == "Date": date = h["value"]
            email_list.append({
                "id": msg["id"],
                "from": sender,
                "subject": subject,
                "date": date,
                "snippet": detail.get("snippet", "")
            })
        return email_list
    except Exception as e:
        return f"Error: {e}"

def run_get_email(service, email_id):
    try:
        email = service.users().messages().get(userId="me", id=email_id).execute()
        headers = email.get("payload", {}).get("headers", [])
        subject, sender, date = "No Subject", "Unknown", "Unknown"
        for h in headers:
            if h["name"] == "Subject": subject = h["value"]
            elif h["name"] == "From": sender = h["value"]
            elif h["name"] == "Date": date = h["value"]
        body = get_body_from_payload(email.get("payload", {})) or email.get("snippet", "")
        return {
            "id": email_id,
            "from": sender,
            "subject": subject,
            "date": date,
            "body": body.strip()
        }
    except Exception as e:
        return f"Error fetching details: {e}"

def run_send_email(service, to, subject, body):
    try:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Successfully sent email to {to}. Message ID: {sent['id']}"
    except Exception as e:
        return f"Failed to send email: {e}"

def run_create_draft(service, to, subject, body):
    try:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
        return f"Successfully created draft for {to}. Draft ID: {draft['id']}"
    except Exception as e:
        return f"Failed to create draft: {e}"

# --- Agent Chat Endpoints ---

class ChatRequest(BaseModel):
    prompt: str
    email: str
    history: List[dict] = []

def call_nvidia_llm(messages):
    if not NVIDIA_API_KEY:
        raise HTTPException(status_code=500, detail="NVIDIA_API_KEY environment variable is not configured.")
        
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "qwen/qwen3.5-122b-a10b",
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.1,
        "top_p": 0.95,
        "stream": False
    }
    
    try:
        response = requests.post(NVIDIA_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return json.dumps({
            "thought": f"Error communicating with LLM API: {e}",
            "final_response": "I hit an error communicating with the AI model."
        })

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Processes user prompt and loops agent tools dynamically using LLM instructions."""
    # Obtain user Gmail credentials
    try:
        creds = get_credentials(request.email)
        service = build("gmail", "v1", credentials=creds)
    except HTTPException as he:
        return JSONResponse(status_code=he.status_code, content={"detail": he.detail})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Gmail Auth failed: {e}"})

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

    messages = [{"role": "system", "content": system_instruction}]
    
    # Add context history
    for item in request.history:
        messages.append({"role": item["role"], "content": item["content"]})
        
    messages.append({"role": "user", "content": request.prompt})
    
    # We run the ReAct loop step-by-step up to 5 iterations
    last_thought = ""
    last_tool_run = {}
    
    for step in range(5):
        response_text = call_nvidia_llm(messages)
        
        # Clean formatting
        clean_text = response_text.strip()
        if clean_text.startswith("```json"): clean_text = clean_text[7:]
        if clean_text.startswith("```"): clean_text = clean_text[3:]
        if clean_text.endswith("```"): clean_text = clean_text[:-3]
        clean_text = clean_text.strip()
        
        try:
            response_data = json.loads(clean_text)
        except Exception:
            return {
                "thought": "Agent generated non-JSON content.",
                "final_response": response_text
            }
            
        last_thought = response_data.get("thought", "")
        
        if "final_response" in response_data:
            # Task finished
            return {
                "thought": last_thought,
                "final_response": response_data["final_response"],
                "tool": last_tool_run.get("tool"),
                "tool_input": last_tool_run.get("input"),
                "tool_result": last_tool_run.get("result")
            }
            
        action = response_data.get("action")
        action_input = response_data.get("action_input", {})
        
        if not action:
            return {
                "thought": last_thought,
                "final_response": "Failed to determine next agent step."
            }
            
        # Execute tool
        if action == "list_emails":
            result = run_list_emails(service, query=action_input.get("query"), max_results=action_input.get("max_results", 5))
        elif action == "get_email":
            result = run_get_email(service, action_input.get("email_id"))
        elif action == "send_email":
            result = run_send_email(service, action_input.get("to"), action_input.get("subject"), action_input.get("body"))
        elif action == "create_draft":
            result = run_create_draft(service, action_input.get("to"), action_input.get("subject"), action_input.get("body"))
        else:
            result = f"Error: Tool '{action}' not found."
            
        last_tool_run = {
            "tool": action,
            "input": action_input,
            "result": result
        }
        
        # Add to message thread to continue loop
        messages.append({"role": "assistant", "content": response_text})
        messages.append({"role": "user", "content": f"Tool execution result:\n{json.dumps(result)}"})
        
    return {
        "thought": last_thought,
        "final_response": "I ran out of execution steps before finding a final response.",
        "tool": last_tool_run.get("tool"),
        "tool_input": last_tool_run.get("input"),
        "tool_result": last_tool_run.get("result")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="localhost", port=8000, reload=True)
