"""
Bot callback endpoints — §6.2 of enterprise-evolution-blueprint.

Feishu event callback (message receive + reaction). Extensible for
DingTalk, WeCom in future phases.
"""

import json
import hmac

from fastapi import APIRouter, HTTPException, Request

from services.bot_handler import BotHandler
from services.feishu_client import FeishuClient
from errors import ErrorCode, ErrorContext, UpstreamUnavailableError
from logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/bot/feishu")
async def feishu_callback(request: Request):
    """Feishu event callback endpoint."""
    body = await request.body()
    body_data = json.loads(body)

    # Signature verification (if configured)
    client = FeishuClient()
    if client.encrypt_key:
        timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = request.headers.get("X-Lark-Request-Nonce", "")
        signature = request.headers.get("X-Lark-Signature", "")
        if not (timestamp and nonce and signature):
            raise HTTPException(status_code=401, detail="Missing signature headers")
        if not client.verify_signature(timestamp, nonce, body, signature):
            logger.warning("feishu_signature_failed")
            raise HTTPException(status_code=403, detail="Invalid signature")
    elif client.verification_token:
        # Feishu v2/header events carry the token in header; v1 uses body.token.
        header = body_data.get("header")
        token = (header.get("token") if isinstance(header, dict) else None) if (
            "schema" in body_data or "header" in body_data
        ) else body_data.get("token")
        if not isinstance(token, str) or not hmac.compare_digest(
            token.encode("utf-8"), client.verification_token.encode("utf-8")
        ):
            raise HTTPException(status_code=401, detail="Invalid verification token")

    # URL verification is authenticated by the same configured mode as events.
    if body_data.get("type") == "url_verification":
        return {"challenge": body_data.get("challenge", "")}

    # Handle event
    event = body_data.get("event", {})
    event_type = event.get("type", body_data.get("type", ""))
    handler = BotHandler()
    try:
        result = handler.handle_event(event_type, event)
        if result:
            return result
    except Exception as e:  # noqa: BLE001  # Bot 事件处理失败仅记录并回复错误卡片，不影响回调端点返回 200
        logger.error("bot_handler_error", error=str(e))
        if client.configured:
            chat_id = event.get("message", {}).get("chat_id", "")
            if chat_id:
                card = client.build_error_card()
                client.reply_card(chat_id, card)

    return {"status": "ok"}


@router.get("/bot/config")
async def bot_config():
    """Get bot configuration status."""
    client = FeishuClient()
    return {
        "feishu": {
            "configured": client.configured,
            "app_id": client.app_id[:6] + "***" if client.app_id else "",
            "verification_configured": bool(client.verification_token),
        },
    }


@router.put("/bot/config/{platform}")
async def update_bot_config(platform: str, body: dict):
    """Update bot configuration. Platform: feishu | dingtalk | wecom."""
    if platform == "feishu":
        for key in ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_VERIFICATION_TOKEN",
                     "FEISHU_ENCRYPT_KEY"]:
            if key.lower().replace("feishu_", "").replace("_", " ") in body:
                # Config values are set via .env, API just reports
                pass
        return {"status": "config_note", "message": "Bot config managed via .env file"}
    raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")


@router.post("/bot/feishu/alert")
async def feishu_alert_webhook(request: Request):
    """AlertManager webhook receiver for Prometheus alerts → Feishu."""
    body = await request.json()
    alerts = body.get("alerts", [])
    client = FeishuClient()
    if client.configured:
        for alert in alerts[:5]:  # Max 5 alert cards per batch
            status = alert.get("status", "firing")
            annotations = alert.get("annotations", {})
            labels = alert.get("labels", {})
            severity = labels.get("severity", "warning")
            alert_name = labels.get("alertname", "Unknown")

            card = client.build_error_card(
                message=annotations.get("summary", annotations.get("description", "")),
            )
            card["header"]["title"]["content"] = (
                f"{'🔴' if severity == 'critical' else '🟡'} [{status.upper()}] {alert_name}"
            )
            try:
                # Send to default chat (configured via env FEISHU_ALERT_CHAT_ID)
                import os
                chat_id = os.getenv("FEISHU_ALERT_CHAT_ID", "")
                if chat_id:
                    client.reply_card(chat_id, card)
            except Exception:  # noqa: S110, BLE001  # 飞书告警卡片投递为 fire-and-forget，失败不阻塞告警接收
                pass
    return {"status": "received", "alert_count": len(alerts)}


@router.post("/bot/config/{platform}/test")
async def test_bot(platform: str):
    """Send a test message via bot."""
    if platform == "feishu":
        client = FeishuClient()
        if not client.configured:
            raise HTTPException(status_code=400, detail="Feishu bot not configured")
        try:
            token = client._get_tenant_token()
            return {"status": "ok", "message": f"Tenant token obtained: {token[:8]}..."}
        except Exception as e:
            raise UpstreamUnavailableError(
                "飞书连接测试失败",
                code=ErrorCode.UPSTREAM_UNAVAILABLE,
                context=ErrorContext(provider="feishu"),
            ) from e
    raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
