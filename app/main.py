
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.agent import handle_message, get_agent_mode
from app.schemas import ChatRequest, ChatResponse


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="SupportFlow AI",
    description="AI-powered customer support agent with business tool execution.",
    version="1.0.0",
)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "SupportFlow AI",
        "agent_mode": get_agent_mode(),
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    message = request.message.strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    if len(message) > 4000:
        raise HTTPException(
            status_code=400,
            detail="Message is too long. Maximum length is 4000 characters.",
        )

    try:
        result = handle_message(
            message=message,
            conversation_id=request.conversation_id,
        )

        return ChatResponse(**result)

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the message.",
        )


# Serve the frontend from the same application.
app.mount(
    "/",
    StaticFiles(directory=STATIC_DIR, html=True),
    name="static",
)
