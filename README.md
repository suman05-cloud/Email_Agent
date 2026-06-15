# Email Agent & LLM Chat Integration

This project contains two components:
1. **Gmail Integration (`app.py`)**: Fetches and displays the last 3 primary messages from your Gmail inbox using the Google Gmail API.
2. **NVIDIA LLM Integration (`test.py`)**: A command-line chatbot interface powered by Qwen-3.5 via the NVIDIA API.

---

## Project Structure

```text
Email_Agent/
├── .env.example        # Template for environment variables
├── .gitignore          # Git exclusion rules (keeps secrets out of Git)
├── app.py              # Gmail API script
├── requirements.txt    # Python dependencies
└── test.py             # NVIDIA LLM chatbot script
```

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd Email_Agent
```

### 2. Set Up a Virtual Environment (Optional but Recommended)
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables & Credentials

#### NVIDIA API Key (For `test.py`)
1. Duplicate `.env.example` and rename it to `.env`:
   ```bash
   copy .env.example .env
   ```
2. Open `.env` and replace `your_nvidia_api_key_here` with your actual NVIDIA API key:
   ```env
   NVIDIA_API_KEY=nvapi-...
   ```

#### Google Gmail Credentials (For `app.py`)
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project, enable the **Gmail API**, and configure the **OAuth consent screen** (Internal or External with test users).
3. Create **OAuth 2.0 Client IDs** credential and download the credentials JSON file.
4. Save the downloaded JSON file in the root of this repository as `credentials.json`.
5. The first time you run `app.py`, a browser window will open asking you to authenticate. Once completed, a `token.json` file will automatically be created to store your session token.

---

## How to Run

### Run NVIDIA LLM Chat
```bash
python test.py
```

### Run Gmail Agent
```bash
python app.py
```

---

## Security Notes

> [!IMPORTANT]
> The following sensitive files are excluded from git tracking via `.gitignore` to prevent secret leaks:
> - `.env` (contains API keys)
> - `credentials.json` (contains Google OAuth client ID/secret)
> - `token.json` (contains user authentication sessions)
>
> Never commit or upload these files to GitHub or any public code hosting platform.
