from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app.extensions import db
from app.models import AiChatUsage, utcnow
from app.services.ai import AiServiceError, build_chat_messages, chat_once, estimate_cost

bp = Blueprint("ai", __name__, url_prefix="/api/ai")

MAX_MESSAGE_LENGTH = 500
MAX_REQUESTS_PER_MINUTE = 10


def _rate_limited():
    """简单限流：同一用户每分钟最多 MAX_REQUESTS_PER_MINUTE 次提问，防止接口被刷。"""
    minute_ago = utcnow() - timedelta(minutes=1)
    recent = AiChatUsage.query.filter(
        AiChatUsage.user_id == current_user.id,
        AiChatUsage.created_at >= minute_ago,
    ).count()
    return recent >= MAX_REQUESTS_PER_MINUTE


@bp.post("/chat")
def chat():
    if not current_user.is_authenticated:
        return jsonify(error="请先登录后再使用 AI 助手。"), 401
    if not current_app.config["DEEPSEEK_API_KEY"]:
        return jsonify(error="AI 助手暂未开放，请稍后再试。"), 503

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="请输入你的问题。"), 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify(error=f"问题长度不能超过 {MAX_MESSAGE_LENGTH} 字。"), 400
    if _rate_limited():
        return jsonify(error="提问太频繁了，请稍后再试。"), 429

    messages = build_chat_messages(message)
    try:
        reply, usage = chat_once(messages)
    except AiServiceError as error:
        db.session.rollback()
        return jsonify(error=str(error)), 502

    record = AiChatUsage(
        user_id=current_user.id,
        model=current_app.config["DEEPSEEK_MODEL"],
        prompt_tokens=int((usage or {}).get("prompt_tokens") or 0),
        completion_tokens=int((usage or {}).get("completion_tokens") or 0),
        total_tokens=int((usage or {}).get("total_tokens") or 0),
        cost=estimate_cost(usage),
    )
    db.session.add(record)
    db.session.commit()
    return jsonify(reply=reply)
