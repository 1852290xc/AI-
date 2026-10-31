"""发布页的 AI 助手：识别类型 / 型号 / 成色，估算价值并给建议（仅建议，不强制）。

复用 ai_engine 的分类与成色折价表，不依赖任何外部服务。
"""
import re

from ai_engine import CONDITION_DISCOUNT, classify_product

MODEL_PATTERNS = [
    r"(iphone\s*\d{1,2}\s*(?:pro|plus|mini|max)?)",
    r"(ipad\s*(?:air|pro|mini)?\s*\d{0,2})",
    r"(macbook\s*(?:air|pro)?(?:\s*m\d)?)",
    r"(airpods\s*(?:pro)?\s*\d?)",
    r"\b((?:redmi|honor|oppo|vivo|xiaomi)\s*[a-z]*\s*\d{1,2}[a-z]*)\b",
    r"\b([a-z]{1,4}\d{2,4}[a-z]{0,3})\b",
    r"\b(\d{2,3}\s*g(?:b)?)\b",
    r"(\d{2,3}\s*键)",
    r"(\d{2}\s*寸)",
    r"\b(\d{2,3}\s*码)\b",
]

CONDITION_WORDS = [
    ("全新", ["全新", "未拆", "未使用", "仅拆封", "开封未用"]),
    ("九成新", ["九成新", "9成新", "九五新", "几乎全新", "无使用痕迹", "基本全新"]),
    ("八成新", ["八成新", "8成新", "轻微痕迹", "轻微划痕", "轻微使用"]),
    ("七成新", ["七成新", "7成新", "明显划痕", "使用痕迹明显", "有磨损"]),
    ("有瑕疵", ["有瑕疵", "破损", "磕碰", "掉漆"]),
]

BASE_PRICE = [
    (["iphone", "苹果手机"], 3200),
    (["ipad", "平板"], 2600),
    (["macbook", "笔记本", "电脑"], 4200),
    (["耳机", "airpods"], 400),
    (["键盘"], 260),
    (["鼠标"], 120),
    (["显示器"], 700),
    (["相机"], 2200),
    (["手表"], 800),
    (["教材", "课本", "高数", "线代", "概率论"], 45),
    (["考研", "真题", "四六级"], 60),
    (["台灯"], 70),
    (["电煮锅", "锅"], 110),
    (["收纳"], 50),
    (["篮球"], 160),
    (["羽毛球"], 140),
    (["跑鞋", "鞋"], 220),
    (["羽绒服", "外套"], 420),
    (["包"], 180),
    (["颜料", "画笔"], 46),
    (["尤克里里", "吉他"], 260),
]


def detect_condition(text):
    t = (text or "").lower()
    for cond, words in CONDITION_WORDS:
        for w in words:
            if w.lower() in t:
                return cond, w
    return "", ""


def extract_model(title, description=""):
    text = f"{title or ''} {description or ''}".lower()
    found = []
    for pat in MODEL_PATTERNS:
        for m in re.finditer(pat, text):
            val = m.group(1).strip()
            if val and val not in found:
                found.append(val)
    pretty = []
    for f in found:
        for key, brand in (("iphone", "iPhone"), ("ipad", "iPad"),
                           ("macbook", "MacBook"), ("airpods", "AirPods")):
            if f.startswith(key):
                f = brand + f[len(key):]
        pretty.append(f)
    return pretty[:3]


def _median(values):
    values = sorted(v for v in values if v and v > 0)
    if not values:
        return 0
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def estimate_value(title, description="", category="", condition="", original_price=0,
                   comparables=None, model=None):
    """优先用“同型号”可比价，其次原价折算，最后词表兜底。"""
    comparables = comparables or []
    cond = condition or "九成新"
    tokens = [t.lower() for t in (model or []) if len(str(t)) >= 2]

    prices = []
    for c in comparables:
        if isinstance(c, dict):
            price = c.get("price") or 0
            name = (c.get("title") or "").lower()
            if not price or price <= 0:
                continue
            # 有型号时只认同型号的可比价
            if tokens and not any(t in name for t in tokens):
                continue
            prices.append(price)
        elif c and c > 0:
            prices.append(c)

    if len(prices) >= 3:
        mid = _median(prices)
        source = f"参考了 {len(prices)} 件同型号商品的成交/在售价"
    elif original_price and float(original_price) > 0:
        mid = float(original_price) * CONDITION_DISCOUNT.get(cond, 0.6)
        source = f"按原价 {float(original_price):.0f} 元 × {CONDITION_DISCOUNT.get(cond, 0.6):.2f}（{cond}）折算"
    else:
        text = f"{title} {description}".lower()
        base = 0
        for words, price in BASE_PRICE:
            if any(w in text for w in words):
                base = price
                break
        mid = (base or 300) * CONDITION_DISCOUNT.get(cond, 0.6)
        source = "同品类暂无可比数据，按常见行情估算"

    low = max(5, round(mid * 0.85))
    high = max(low + 5, round(mid * 1.12))
    return {"low": int(low), "mid": int(round(mid)), "high": int(high),
            "source": source, "count": len(prices)}


def build_advice(model, condition, value, has_image=False, original_price=0):
    tips = []
    if not model:
        tips.append("标题里补上型号（如 iPhone 13 128G），买家更容易搜到")
    if not condition:
        tips.append("描述里写清成色细节（划痕、电池健康、配件），议价空间更小")
    if not original_price:
        tips.append("填上原价，估价会更贴近你的实际入手成本")
    if not has_image:
        tips.append("配一张实拍图，同价位下点击率通常高一倍")
    if value["mid"] - value["low"] >= 10:
        tips.append(f"建议挂 ¥{value['mid']}，留出 ¥{value['mid'] - value['low']} 的议价空间")
    tips.append("以上都只是建议，最终价格由你决定")
    return tips[:4]


def analyze_listing(title, description, original_price=0, comparables=None, has_image=False):
    cls = classify_product(title, description)
    text = f"{title} {description}"
    cond, cond_hit = detect_condition(text)
    model = extract_model(title, description)
    value = estimate_value(title, description, cls["category"], cond, original_price, comparables, model)
    advice = build_advice(model, cond, value, has_image, original_price)
    return {
        "category": cls["category"],
        "confidence": cls["confidence"],
        "condition": cond,
        "condition_hit": cond_hit,
        "model": model,
        "value": value,
        "advice": advice,
    }
