"""Static resource serving — Engine-Vue chat-widget.js."""

import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend", "public")


@router.get("/static/chat-widget.js")
async def chat_widget_js():
    path = os.path.join(_STATIC_DIR, "chat-widget.js")
    if not os.path.exists(path):
        # Fallback: running inside Docker where frontend/public is not available
        alt = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public", "chat-widget.js")
        if os.path.exists(alt):
            path = alt
    return FileResponse(path, media_type="application/javascript")
