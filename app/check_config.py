import os
import sys

def main():
    required = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [k for k in required if not os.getenv(k, "").strip()]
    if missing:
        print("Missing required environment variables: " + ", ".join(missing))
        return 2

    gemini = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini:
        try:
            from google import genai
            client = genai.Client(api_key=gemini)
            model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            info = client.models.get(model=model)
            print(f"Gemini configuration OK: {getattr(info, 'name', model)}")
        except Exception as exc:
            print(f"Gemini check failed; fallback mode remains available: {exc}")
    else:
        print("GEMINI_API_KEY not set: deterministic fallback mode is enabled.")

    print("Required Telegram variables are present.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
