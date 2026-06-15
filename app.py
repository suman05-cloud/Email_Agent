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

# Open browser for login
creds = None

if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json",SCOPES)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)

    with open("token.json", "w") as token_file:
        token_file.write(creds.to_json())


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