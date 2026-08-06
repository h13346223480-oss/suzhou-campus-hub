"""AI 助手服务：调用 DeepSeek（OpenAI 兼容）对话接口并估算费用。"""
import json
import re
import urllib.error
import urllib.request

from flask import current_app
from sqlalchemy import or_

from app.models import AiKnowledge, Guide, Post

SYSTEM_PROMPT = (
    "你是东蒙Assistant，东蒙Hub（东南大学苏州校区学生自发建设的非官方校园信息平台）的智能助手，"
    "面向首届本科生解答校园学习与生活问题，例如报到注册、宿舍、交通、食堂、全英课堂、"
    "学习资源、校园互助等。请使用简体中文，回答简洁、实用、友好。"
    "注意：本平台是学生自发的非官方平台；涉及学校官方政策或重要通知时，"
    "请提醒用户以学校官方信息为准，不要编造具体细节。"
)

MAX_KNOWLEDGE_HITS = 4
ARTICLES_LIMIT = 3
ARTICLE_EXCERPT_CHARS = 500


def _query_substrings(query, min_len=2, max_len=11):
    """取查询串长度为 min_len-max_len 的连续子串，用于中文无空格场景的标题/关键词匹配。"""
    length = len(query)
    subs = set()
    for start in range(length):
        for end in range(start + min_len, min(start + max_len + 1, length + 1)):
            subs.add(query[start:end])
    return subs


def collect_knowledge_context(query, limit=MAX_KNOWLEDGE_HITS):
    """按相关性匹配活跃知识条目，返回命中的条目列表（得分从高到低，最多 limit 条）。

    打分规则：提问包含完整标题 +100；每个直接命中的关键词 +40；
    提问中 ≥3 字的连续子串出现在标题中则按子串长度加分。
    用 ≥3 字子串匹配可避免“宿舍/多少”这类通用词造成的误命中。
    """
    if not query:
        return []
    q = query.lower()
    title_substrings = _query_substrings(q, min_len=3, max_len=11)
    scored = []
    entries = AiKnowledge.query.filter_by(is_active=True).all()
    for entry in entries:
        title = (entry.title or "").lower()
        keywords = [k.strip().lower() for k in (entry.keywords or "").split(",") if k.strip()]
        score = 0
        if title and title in q:
            score += 100
        for keyword in keywords:
            if keyword and keyword in q:
                score += 40
        if title:
            for substring in title_substrings:
                if substring in title:
                    score += len(substring)
        if score > 0:
            scored.append((score, entry.id, entry))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [entry for _, _, entry in scored[:limit]]


def _excerpt(text, limit=ARTICLE_EXCERPT_CHARS):
    """把正文压缩成适合注入上下文的片段：去首尾空白、合并多余空行、超长截断。"""
    text = (text or "").strip().replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def collect_article_blocks(query, limit=ARTICLES_LIMIT):
    """自动收集与提问相关的已发布内容，供模型参考（社区帖子/新生指南）。

    检索范围：审核通过的帖子（Post.status == 'approved'）与已发布的指南（Guide.status == 'published'）。
    返回 [(label, title, excerpt)]，最多 limit 条，按最近更新优先。
    """
    if not query:
        return []
    q = query.lower()
    substrings = _query_substrings(q, min_len=3, max_len=11)
    # 优先用较长的子串做 SQL 预筛，减少载入的正文量
    bigrams = sorted(substrings, key=len, reverse=True)[:6]
    hits = []

    sources = (
        (Post, Post.status == "approved", "社区帖子"),
        (Guide, Guide.status == "published", "新生指南"),
    )
    for model, status_expr, label in sources:
        clauses = []
        for bigram in bigrams:
            clauses.append(model.title.contains(bigram))
            clauses.append(model.content.contains(bigram))
        if not clauses:
            continue
        candidates = (model.query.filter(status_expr, or_(*clauses))
                      .order_by(model.updated_at.desc())
                      .limit(40).all())
        for row in candidates:
            title = (row.title or "").lower()
            text = (row.content or "").lower()
            if not (any(s in title for s in substrings) or any(s in text for s in substrings)):
                continue
            hits.append((label, row.title, _excerpt(row.content)))
            if len(hits) >= limit:
                break
        if len(hits) >= limit:
            break
    return hits


def build_chat_messages(user_message):
    """组装发给模型的 messages，把命中的知识库条目与相关文章内容作为系统上下文注入。"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    hits = collect_knowledge_context(user_message)
    if hits:
        blocks = [f"【{entry.title}】\n{entry.content}" for entry in hits]
        messages.append({
            "role": "system",
            "content": "以下是东蒙Hub 已整理的校园信息，请优先依据这些内容回答，不要与之冲突：\n\n" + "\n\n".join(blocks),
        })
    article_hits = collect_article_blocks(user_message)
    if article_hits:
        blocks = [f"【{label}：{title}】\n{excerpt}" for label, title, excerpt in article_hits]
        messages.append({
            "role": "system",
            "content": ("以下是东蒙Hub 社区文章中与提问相关的内容（学生自发发布，仅供参考，"
                        "不代表学校官方立场；与已整理信息冲突时以已整理信息为准）：\n\n"
                        + "\n\n".join(blocks)),
        })
    messages.append({"role": "user", "content": user_message})
    return messages


class AiServiceError(Exception):
    """调用 AI 服务失败（携带面向用户的错误信息）。"""


def chat_once(messages):
    """调用 DeepSeek chat/completions 接口。

    返回 (reply_text, usage)，usage 为响应中的用量 dict（可能为 None）。
    失败时抛出 AiServiceError。
    """
    payload = {
        "model": current_app.config["DEEPSEEK_MODEL"],
        "messages": messages,
        "stream": False,
    }
    request = urllib.request.Request(
        current_app.config["DEEPSEEK_BASE_URL"] + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + current_app.config["DEEPSEEK_API_KEY"],
        },
        method="POST",
    )
    timeout = current_app.config["AI_REQUEST_TIMEOUT"]
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            detail = error.read().decode("utf-8")[:300]
        except Exception:
            pass
        raise AiServiceError(f"模型服务返回错误（HTTP {error.code}）：{detail}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise AiServiceError("模型服务暂时不可用，请稍后再试。") from error

    try:
        reply = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise AiServiceError("模型服务返回了无法解析的结果，请稍后再试。") from error
    return reply, body.get("usage")


def estimate_cost(usage):
    """根据 DeepSeek 用量与单价估算费用（元）。缓存命中输入按缓存价计费。"""
    if not usage:
        return 0
    prompt_total = int(usage.get("prompt_tokens") or 0)
    hit = int(usage.get("prompt_cache_hit_tokens") or 0)
    miss = max(prompt_total - hit, 0)
    completion = int(usage.get("completion_tokens") or 0)
    price_in = float(current_app.config["DEEPSEEK_INPUT_PRICE_PER_1M"])
    price_hit = float(current_app.config["DEEPSEEK_INPUT_CACHE_HIT_PRICE_PER_1M"])
    price_out = float(current_app.config["DEEPSEEK_OUTPUT_PRICE_PER_1M"])
    cost = (miss * price_in + hit * price_hit + completion * price_out) / 1_000_000
    return round(cost, 6)
