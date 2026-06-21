
import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# NVIDIA API endpoint
invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

# Retrieve API Key from environment variables
API_KEY = os.getenv("NVIDIA_API_KEY")
if not API_KEY:
    raise ValueError("NVIDIA_API_KEY is not set. Please create a .env file with NVIDIA_API_KEY=<your_key>.")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "text/event-stream"
}

# Take prompt from user
user_prompt = input("Enter your prompt: ")

payload = {
    "model": "qwen/qwen3.5-122b-a10b",
    "messages": [
        {
            "role": "user",
            "content": user_prompt
        }
    ],
    "max_tokens": 512,
    "temperature": 0.6,
    "top_p": 0.95,
    "stream": True
}

try:
    response = requests.post(
        invoke_url,
        headers=headers,
        json=payload,
        stream=True
    )

    response.raise_for_status()

    print("\nAssistant:\n", end="", flush=True)

    for line in response.iter_lines():
        if line:
            line = line.decode("utf-8")

            # Skip non-data lines
            if not line.startswith("data: "):
                continue

            data = line[6:]  # Remove "data: "

            if data == "[DONE]":
                break

            try:
                chunk = json.loads(data)
                content = chunk["choices"][0]["delta"].get("content", "")
                print(content, end="", flush=True)
            except Exception:
                pass

    print()  # New line after completion

except Exception as e:
    print("Error:", e)