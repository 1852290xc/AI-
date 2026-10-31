"""可选的大模型适配层（OpenAI 兼容接口）。

设计原则：**有 key 才用，出错就退**。任何异常都返回 None，调用方自动回落到
search_engine 的本地检索，因此没网、没 key、超时都不会影响主流程。

环境变量：
    LLM_API_KEY    必填，没有这个就整体关闭
    LLM_BASE_URL   可选，默认 https://api.deepseek.com/v1
    LLM_MODEL      可选，默认 deepseek-chat
"""
import json
import os
import threading
import time
import urllib.request

API_KEY = os.getenv("LLM_API_KEY", "").strip()
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "6"))

_cache = {}
_lock = threading.Lock()


def enabled():
    return bool(API_KEY)


def _chat(messages, max_tokens=300, temperature=0.2):
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        body = json.loads(r.read().decode())
    return body["choices"][0]["message"]["content"]


def _json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.split("\n", 1)[1] if "\n" in text else text
    return json.loads(text)


def _cached(key, fn):
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < 300:
            return hit[1]
    value = fn()
    with _lock:
        _cache[key] = (time.time(), value)
    return value


def expand_query(query):
    """把口语查询拆成检索词 + 意图。失败返回 None。"""
    if not enabled():
        return None

    def run():
        try:
            content = _chat([
                {"role": "system", "content":
                 "你是校园二手平台的搜索意图解析器。只输出 JSON，不要解释。"},
                {"role": "user", "content":
                 f"用户搜索词：{query}\n"
                 "请输出 {\"keywords\": [3-6 个用于检索的中文/英文关键词], "
                 "\"intent\": \"一句话概括用户想找什么\", "
                 "\"category\": \"数码电子|教材书籍|生活用品|运动户外|服饰美妆|其他 之一，无法判断填 其他\"}"},
            ], max_tokens=200)
            data = _json(content)
            kws = [str(k).strip() for k in data.get("keywords", []) if str(k).strip()]
            return {"keywords": kws[:6], "intent": data.get("intent", ""),
                    "category": data.get("category", ""), "source": "llm"}
        except Exception:
            return None

    return _cached(f"expand:{query}", run)


def rerank(query, rows, top_n=10):
    """让模型按“用户会不会想点”重排候选，并给出理由。失败返回 None。"""
    if not enabled() or not rows:
        return None

    def run():
        try:
            brief = [
                {"id": r["product"].id, "title": r["product"].title,
                 "price": r["product"].price, "condition": r["product"].condition}
                for r in rows[:20]
            ]
            content = _chat([
                {"role": "system", "content":
                 "你是校园二手平台的搜索排序器。只输出 JSON，不要解释。"},
                {"role": "user", "content":
                 f"搜索词：{query}\n候选商品：{json.dumps(brief, ensure_ascii=False)}\n"
                 "请按与搜索意图的相关度排序，输出 "
                 "{\"order\": [商品id 从高到低], \"reasons\": {\"商品id\": \"8 字以内的推荐理由\"}}"},
            ], max_tokens=500)
            data = _json(content)
            order = [int(i) for i in data.get("order", [])]
            reasons = {int(k): str(v)[:16] for k, v in (data.get("reasons") or {}).items()}
            by_id = {r["product"].id: r for r in rows}
            out = []
            for pid in order:
                if pid in by_id:
                    row = dict(by_id[pid])
                    row["reason"] = reasons.get(pid, row["reason"])
                    row["source"] = "llm"
                    out.append(row)
            return out or None
        except Exception:
            return None

    return _cached(f"rerank:{query}:{len(rows)}", run)


def status():
    return {
        "enabled": enabled(),
        "model": MODEL if enabled() else "",
        "base_url": BASE_URL if enabled() else "",
    }
