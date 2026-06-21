import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Read-only access
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Load OAuth credentials
flow = InstalledAppFlow.from_client_secrets_file(
    "credentials.json",
    SCOPES
)

# Tokens directory settings
TOKENS_DIR = "tokens"
os.makedirs(TOKENS_DIR, exist_ok=True)

# Find existing token accounts
existing_accounts = []
if os.path.exists(TOKENS_DIR):
    existing_accounts = [f[:-5] for f in os.listdir(TOKENS_DIR) if f.endswith(".json")]

selected_email = None

if existing_accounts:
    print("Available Gmail accounts:")
    for i, email in enumerate(existing_accounts, 1):
        print(f"[{i}] {email}")
    print(f"[{len(existing_accounts) + 1}] Login with a new account")
    
    choice = input(f"Select an account to use (1-{len(existing_accounts) + 1}): ").strip()
    try:
        choice_idx = int(choice) - 1
        if 0 <= choice_idx < len(existing_accounts):
            selected_email = existing_accounts[choice_idx]
    except ValueError:
        pass

creds = None
token_path = None

if selected_email:
    token_path = os.path.join(TOKENS_DIR, f"{selected_email}.json")
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

# Open browser for login if not authenticated
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if token_path:
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)
        
        # Build a temporary service to fetch user email address
        temp_service = build("gmail", "v1", credentials=creds)
        profile = temp_service.users().getProfile(userId="me").execute()
        user_email = profile.get("emailAddress", "unknown_user").lower()
        
        token_path = os.path.join(TOKENS_DIR, f"{user_email}.json")
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
        print(f"\nSuccessfully authenticated and saved token for: {user_email}\n")



# Build Gmail service
service = build("gmail", "v1", credentials=creds)

# Fetch last 3 messages
results = service.users().messages().list(
    userId="me",
    q="in:inbox category:primary",
    maxResults=3
).execute()

messages = results.get("messages", [])

print(f"Found {len(messages)} messages\n")

for msg in messages:
    email = service.users().messages().get(
        userId="me",
        id=msg["id"]
    ).execute()

    subject = "No Subject"
    sender = "Unknown"

    for header in email["payload"]["headers"]:
        if header["name"] == "Subject":
            subject = header["value"]
        elif header["name"] == "From":
            sender = header["value"]

    print("From   :", sender)
    print("Subject:", subject)
    print("-" * 50)