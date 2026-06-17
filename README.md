# AI Email Agent (Decoupled React + FastAPI)

This is a multi-user, production-ready AI Email Automation Agent. It features a React frontend that replicates a premium, ChatGPT-inspired conversational client, and a FastAPI python backend that manages Google OAuth, session profiles, and an autonomous ReAct loop powered by the NVIDIA Qwen-3.5 model.

---

## Project Structure

```text
Email_Agent/
├── Front/                # React (Vite) Frontend Application
│   ├── src/              # React components & global styles
│   │   ├── App.jsx       # Main application layout, state & backend hooks
│   │   ├── index.css     # CSS variable configuration & animations
│   │   └── main.jsx
│   ├── package.json      # Node dependencies
│   └── vite.config.js
├── backend.py            # FastAPI Python backend & OAuth router
├── main.py               # Legacy CLI Gmail ReAct loop (reference)
├── app.py                # Legacy CLI Gmail script (reference)
├── requirements.txt      # Python dependencies
├── credentials.json      # Google OAuth Client Credentials (keep local!)
└── tokens/               # Folder where user Google OAuth tokens are stored
```

---

## Setup Instructions

### 1. Prerequisite credentials

1. **NVIDIA API Key**: Open `.env` and configure your API key:
   ```env
   NVIDIA_API_KEY=nvapi-...
   ```
2. **Google Credentials**: Download the **OAuth 2.0 Client credentials JSON** from the Google Cloud Console. Name this file `credentials.json` and place it in the root directory.
   - *OAuth Redirect URI setting in Google Cloud Console*: Under Authorized Redirect URIs, add: `http://localhost:8000/api/auth/callback`.

---

## How to Run

For development, you run both the backend server and frontend development server simultaneously.

### 1. Start the FastAPI Backend
```bash
# In the root directory:
uvicorn backend:app --reload
```
The backend will start running at `http://localhost:8000`.

### 2. Start the React Frontend
```bash
# Open a new terminal tab, navigate to Front folder:
cd Front
npm install       # (If not already installed)
npm run dev
```
The frontend will start running at `http://localhost:5173`. Open this URL in your browser.

---

## Authentication Flow (Multi-User Support)

1. When you load the frontend, click **Gmail Integration** in the bottom-left sidebar.
2. Click **Connect New Gmail Account**.
3. You will be redirected to the Google login page. Select the account you want to connect and grant the necessary permissions.
4. Once completed, Google will redirect you back to the FastAPI backend, which registers your secure refresh token under `tokens/{email}.json`, and redirects you back to the frontend dashboard.
5. You can now select this profile and converse with the email agent!
