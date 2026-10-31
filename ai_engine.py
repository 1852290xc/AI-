"""本地 AI 引擎：7 个能力全部用纯 Python 实现，不依赖任何外部 API，断网可跑。

1. classify_product   智能分类（关键词打分 + 置信度）
2. suggest_price      智能定价（按成色折价，给出区间）
3. generate_copy      AI 文案生成（分类模板 + 成色话术）
4. moderate_text      内容审核（违规词库 + 命中原因）
5. extract_tags       标签提取（成色 / 品类 / 关键词）
6. recommend_products 个性化推荐（内容 50% + 偏好 35% + 热度 15%）
7. chatbot_reply      智能客服（问答库匹配 + 兜底转人工）
"""
import math
import re

# ---------------------------------------------------------------- 规则库
CATEGORY_RULES = {
    "数码电子": ["iphone", "ipad", "苹果", "手机", "笔记本电脑", "电脑", "键盘", "鼠标", "平板",
                 "耳机", "相机", "显示", "显卡", "主机", "switch", "macbook", "充电", "硬盘", "u盘"],
    "教材书籍": ["教材", "课本", "高数", "线代", "概率论", "考研", "真题", "四六级", "笔记", "题集",
                 "参考书", "文献", "词典", "英语", "政治", "专业课"],
    "生活用品": ["台灯", "风扇", "水壶", "被子", "枕头", "收纳", "衣架", "插排", "锅", "路由器"],
    "运动户外": ["篮球", "足球", "羽毛球", "跑鞋", "瑜伽", "哑铃", "自行车", "帐篷", "球拍", "健身"],
    "服饰美妆": ["羽绒服", "外套", "卫衣", "裙子", "鞋", "帽子", "口红", "面膜", "香水", "包"],
    "其他": [],
}

CONDITION_DISCOUNT = {
    "全新": 0.85,
    "九成新": 0.70,
    "八成新": 0.55,
    "七成新": 0.40,
    "有瑕疵": 0.25,
}

BAD_WORDS = {
    "脏话": ["傻逼", "他妈", "操你", "滚蛋", "去死"],
    "违法物品": ["代考", "枪手", "办证", "发票", "迷药", "仿真枪"],
    "违规交易": ["外挂", "破解版", "盗版", "刷单", "代写论文", "水军"],
    "色情低俗": ["约炮", "裸聊", "色情"],
}

COPY_TEMPLATES = {
    "数码电子": "外观{look}，功能全部正常，电池健康良好，配件齐全。{extra}支持当面验机，介意成色慎拍。",
    "教材书籍": "书本{look}，笔记{note}，无缺页无涂改，重点章节有荧光笔标记。适合本学期跟课或备考使用。",
    "生活用品": "日常使用{look}，功能完好，已清洁消毒。宿舍必备，即买即用。",
    "运动户外": "{look}，使用次数不多，无异味无破损。适合入门练习或日常锻炼。",
    "服饰美妆": "{look}，仅试穿/试用，无污渍无破损。尺码不合适故转手，支持看细节图。",
    "其他": "{look}，功能正常，价格可小刀。有疑问欢迎私信，看到秒回。",
}

LOOK_BY_CONDITION = {
    "全新": "全新未拆封",
    "九成新": "无明显使用痕迹",
    "八成新": "有轻微使用痕迹",
    "七成新": "有正常使用痕迹",
    "有瑕疵": "有明显痕迹（已在描述中说明）",
}

FAQ = [
    (["怎么发布", "如何发布", "发布商品", "卖东西"], "在首页点右上角「发布闲置」，填写标题和价格，AI 会自动帮你分类、写文案、给定价建议，确认后即可上架。"),
    (["怎么改价", "改价格", "修改价格", "降价"], "进入「我的商品」，点对应商品的「编辑」，改价格后保存即可；也可以直接私信买家协商。"),
    (["安全", "被骗", "风险", "靠谱"], "建议校内当面交易、当面验货；平台会审核违规内容，并保留订单与私信记录，遇到问题可在订单页发起取消。"),
    (["怎么买", "下单", "购买"], "在商品详情页点「立即购买」即可生成订单，之后可在「我的订单」里确认完成或取消。"),
    (["手续费", "收费", "佣金"], "校园闲置交易目前完全不收费，平台不抽成。"),
    (["联系", "客服", "人工"], "如果这里没有你要的答案，请在商品页私信卖家，或联系管理员（admin 账号）处理。"),
]

STOPWORDS = set("的了和是与在有我你他她它这那一个一些可以支持什么怎么如何".strip())


# ---------------------------------------------------------------- 工具
def _hit_count(text, words):
    text = (text or "").lower()
    return sum(1 for w in words if w and w.lower() in text)


def _normalize_condition(condition):
    condition = (condition or "").strip()
    if condition in CONDITION_DISCOUNT:
        return condition
    for key in CONDITION_DISCOUNT:
        if key.replace("成", "") and key in condition:
            return key
    if "新" in condition:
        return "九成新"
    return "八成新"


# ---------------------------------------------------------------- 1 分类
def classify_product(title, description=""):
    text = f"{title or ''} {description or ''}".lower()
    scores = {}
    for cat, words in CATEGORY_RULES.items():
        scores[cat] = _hit_count(text, words)

    best = max(scores, key=scores.get)
    total = sum(scores.values())
    if total == 0:
        return {"category": "其他", "confidence": 0.35, "scores": scores, "reason": "未命中任何品类关键词，归入其他"}
    confidence = round(min(0.98, 0.55 + 0.45 * scores[best] / total), 2)
    return {"category": best, "confidence": confidence, "scores": scores,
            "reason": f"命中「{best}」关键词 {scores[best]} 个，占比 {scores[best]}/{total}"}


# ---------------------------------------------------------------- 2 定价
def suggest_price(original_price, condition="九成新"):
    try:
        original = float(original_price or 0)
    except (TypeError, ValueError):
        original = 0.0
    cond = _normalize_condition(condition)
    rate = CONDITION_DISCOUNT[cond]
    if original <= 0:
        return {"low": 0, "high": 0, "suggest": 0, "discount": rate, "condition": cond,
                "note": "缺少原价，无法给出建议"}
    mid = original * rate
    low = max(1, round(mid * 0.88, 1))
    high = max(low + 1, round(mid * 1.12, 1))
    return {"low": low, "high": high, "suggest": round(mid, 1), "discount": rate,
            "condition": cond, "note": f"按{cond}、原价 {original:.0f} 元估算"}


# ---------------------------------------------------------------- 3 文案
def generate_copy(title, category="其他", condition="九成新", original_price=0):
    cond = _normalize_condition(condition)
    look = LOOK_BY_CONDITION.get(cond, "成色良好")
    note = "干净无涂改" if cond in ("全新", "九成新") else "有少量标注"
    extra = ""
    if category == "数码电子":
        extra = "自用一年内，无维修记录。"
    tpl = COPY_TEMPLATES.get(category, COPY_TEMPLATES["其他"]).format(look=look, note=note, extra=extra)

    price_hint = ""
    try:
        if float(original_price or 0) > 0:
            p = suggest_price(original_price, cond)
            price_hint = f"参考价 {p['low']:.0f}–{p['high']:.0f} 元，"
    except (TypeError, ValueError):
        price_hint = ""

    head = f"【{title}】{cond}，" if title else ""
    return f"{head}{tpl}{price_hint}价格可小刀，非诚勿扰。"


# ---------------------------------------------------------------- 4 审核
def moderate_text(text):
    text = text or ""
    hits = []
    for reason, words in BAD_WORDS.items():
        for w in words:
            if w in text:
                hits.append({"word": w, "reason": reason})
    if hits:
        return {"passed": False, "reason": hits[0]["reason"],
                "message": f"内容包含违规词「{hits[0]['word']}」，请修改后再发布。", "hits": hits}
    return {"passed": True, "reason": "", "message": "审核通过", "hits": []}


# ---------------------------------------------------------------- 5 标签
def extract_tags(title, description="", category=""):
    text = f"{title or ''} {description or ''}"
    tags = []

    if category:
        tags.append(category)

    for cond in CONDITION_DISCOUNT:
        if cond in text or cond.replace("成新", "成") in text:
            tags.append(cond)
            break

    if re.search(r"\d{4}\s*款|20\d{2}", text):
        m = re.search(r"(20\d{2})\s*款?", text)
        if m:
            tags.append(m.group(1) + "款")

    for word in re.findall(r"[A-Za-z]{2,12}", text):
        low = word.lower()
        if low not in [t.lower() for t in tags] and low not in STOPWORDS:
            tags.append(word)

    for cat, words in CATEGORY_RULES.items():
        for w in words:
            if w in text and w not in tags and len(w) >= 2:
                tags.append(w)
                break

    if "原价" in text or "入手" in text:
        tags.append("有原价")

    seen, out = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:8]


# ---------------------------------------------------------------- 6 推荐
def recommend_products(user, limit=8):
    """内容相似度 50% + 分类偏好 35% + 热度 15%；新用户退化为热门。"""
    from models import Behavior, Category, Product, db

    base = Product.query.filter_by(status="onsale").all()
    if not base:
        return []

    if user is None or not getattr(user, "is_authenticated", False):
        return sorted(base, key=lambda p: p.views or 0, reverse=True)[:limit]

    behaviors = Behavior.query.filter_by(user_id=user.id).order_by(Behavior.id.desc()).limit(60).all()
    if not behaviors:
        return sorted(base, key=lambda p: p.views or 0, reverse=True)[:limit]

    seen_ids = {b.product_id for b in behaviors}
    cat_counter = {}
    token_counter = {}
    for b in behaviors:
        prod = Product.query.get(b.product_id)
        if not prod:
            continue
        if prod.category_id:
            cat_counter[prod.category_id] = cat_counter.get(prod.category_id, 0) + 1
        for t in prod.tag_list:
            token_counter[t] = token_counter.get(t, 0) + 1
    total_cat = sum(cat_counter.values()) or 1
    max_views = max((p.views or 0) for p in base) or 1

    scored = []
    for p in base:
        if p.id in seen_ids and p.seller_id == getattr(user, "id", 0):
            continue
        pref = cat_counter.get(p.category_id, 0) / total_cat
        tokens = set(p.tag_list)
        overlap = len(tokens & set(token_counter)) / max(1, len(tokens))
        heat = (p.views or 0) / max_views
        score = 0.5 * overlap + 0.35 * pref + 0.15 * heat
        scored.append((round(score, 4), p))

    scored.sort(key=lambda x: (x[0], x[1].views or 0), reverse=True)
    return [p for _, p in scored[:limit]]


# ---------------------------------------------------------------- 7 客服
def chatbot_reply(question):
    q = (question or "").strip()
    if not q:
        return {"answer": "你可以问我：怎么发布商品、怎么改价、交易安全吗、平台收费吗。", "matched": False}
    for keywords, answer in FAQ:
        if any(k in q for k in keywords):
            return {"answer": answer, "matched": True}
    return {"answer": "这个问题我还没学会，建议直接私信卖家，或联系管理员（admin 账号）人工处理。", "matched": False}


# ---------------------------------------------------------------- 自测
if __name__ == "__main__":
    print(classify_product("九成新 iPhone 13 128G", "自用，无维修"))
    print(suggest_price(5999, "九成新"))
    print(generate_copy("iPad Air 5", "数码电子", "九成新", 4399))
    print(moderate_text("这是一台好机器"))
    print(moderate_text("低价出外挂，需要的私聊"))
    print(extract_tags("九成新 iPad Air 5 2022款", "自用一年，配件齐全", "数码电子"))
    print(chatbot_reply("怎么发布商品"))
