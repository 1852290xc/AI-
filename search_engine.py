"""本地检索与个性化排序（纯 Python，无第三方依赖）。

- TF-IDF 倒排 + 余弦相似度，中文按二元组切分
- 同义词扩展：把「便宜平板」这类口语查询扩成可命中的词
- 个性化：分类偏好（来自 Behavior）+ 热度，与语义分加权
- 每条结果都给一个可读的推荐理由
"""
import math
import re
from collections import Counter

CJK = re.compile(r"[\u4e00-\u9fa5]")
WORD = re.compile(r"[a-z0-9]+")

SYNONYMS = {
    "手机": ["iphone", "手机", "苹果", "华为", "小米", "三星"],
    "苹果": ["iphone", "ipad", "macbook", "苹果"],
    "电脑": ["笔记本", "电脑", "macbook", "主机", "显示器"],
    "平板": ["ipad", "平板", "air", "pro"],
    "键盘": ["键盘", "键帽", "机械", "轴"],
    "鼠标": ["鼠标", "m590", "罗技"],
    "教材": ["教材", "课本", "书", "笔记"],
    "书": ["教材", "书", "课本", "文献"],
    "考研": ["考研", "真题", "政治", "英语", "专业课"],
    "高数": ["高数", "微积分", "数学", "同济"],
    "台灯": ["台灯", "灯", "护眼", "照明"],
    "篮球": ["篮球", "球", "斯伯丁"],
    "羽毛球": ["羽毛球", "球拍", "拍"],
    "羽绒服": ["羽绒服", "外套", "冬天", "保暖"],
    "鞋": ["鞋", "帆布鞋", "跑鞋", "码"],
    "便宜": ["小刀", "低价", "便宜", "实惠"],
    "全新": ["全新", "未拆", "未使用"],
    "二手": ["二手", "闲置", "转手"],
}

STOP = set("的了和是在有我你他她它这那个一些什么怎么如何可以想要买个件台部")


def tokenize(text):
    """中文二元组 + 英文词，返回 token 列表。"""
    text = (text or "").lower()
    tokens = []
    for w in WORD.findall(text):
        if len(w) >= 2 and w not in STOP:
            tokens.append(w)
    for run in re.findall(r"[\u4e00-\u9fa5]+", text):
        if len(run) == 1:
            tokens.append(run)
            continue
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg not in STOP:
                tokens.append(bg)
        for ch in run:
            if ch not in STOP:
                tokens.append(ch)
    return tokens


def expand(query):
    """口语查询 → 检索词集合（含同义词）。"""
    q = (query or "").strip().lower()
    terms = set(tokenize(q))
    hits = []
    for key, words in SYNONYMS.items():
        if key in q:
            hits.append(key)
            terms.update(tokenize(" ".join(words)))
    # 「便宜的平板」这类意图词：去掉修饰词后仍保留主体
    for w in ("便宜", "实惠", "好看", "新", "旧"):
        terms.discard(w)
    return terms, hits


class Index:
    def __init__(self, products):
        self.products = products
        self.docs = []
        for p in products:
            title = " ".join([p.title or ""] * 3)
            tags = " ".join(p.tag_list or []) * 2
            cat = (p.category.name if p.category else "")
            body = p.description or ""
            text = f"{title} {tags} {cat} {cat} {body}"
            self.docs.append(Counter(tokenize(text)))

        df = Counter()
        for doc in self.docs:
            for t in doc:
                df[t] += 1
        n = max(1, len(self.docs))
        self.idf = {t: math.log((n + 1) / (c + 0.5)) + 1 for t, c in df.items()}
        self.vectors = [self._vec(doc) for doc in self.docs]

    def _vec(self, counter):
        vec = {}
        for t, c in counter.items():
            vec[t] = (1 + math.log(c)) * self.idf.get(t, 1.0)
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def query_vector(self, terms):
        counter = Counter()
        for t in terms:
            counter[t] += 1
        return self._vec(counter)

    def score(self, terms):
        """返回 [(product, cosine, matched_terms)]，按相似度降序。"""
        qv = self.query_vector(terms)
        out = []
        for p, dv in zip(self.products, self.vectors):
            sim = sum(v * dv.get(t, 0.0) for t, v in qv.items())
            matched = [t for t in qv if t in dv and len(t) > 1]
            if sim > 0:
                out.append((p, sim, matched))
        out.sort(key=lambda x: x[1], reverse=True)
        return out


def affinity(user_id, behaviors_by_product, products):
    """分类偏好：最近行为权重更高。"""
    from models import Product

    if not user_id:
        return {}, {}
    cat_count, viewed = Counter(), []
    for b in behaviors_by_product:
        prod = Product.query.get(b.product_id)
        if not prod or not prod.category_id:
            continue
        cat_count[prod.category_id] += 1
        viewed.append(prod)
    total = sum(cat_count.values()) or 1
    return {k: v / total for k, v in cat_count.items()}, viewed


def reason_for(product, matched, cat_pref, viewed_titles):
    if matched:
        nice = "、".join(matched[:3])
        return f"匹配「{nice}」"
    if product.category_id and cat_pref.get(product.category_id, 0) > 0.2:
        return f"你常看{product.category.name}"
    for t in viewed_titles:
        if t and t[:6] == product.title[:6]:
            return "和你之前看过的那件同类"
    return "热门"


def rank(products, query, user=None, behaviors=None, limit=12, fill=False):
    """语义 60% + 分类偏好 25% + 热度 15%。"""
    idx = Index(products)
    terms, hit_terms = expand(query)
    scored = idx.score(terms) if terms else []

    if terms and not scored:
        return [], hit_terms

    cat_pref, viewed = ({}, [])
    if user is not None and getattr(user, "is_authenticated", False):
        cat_pref, viewed = affinity(user.id, behaviors or [], products)
    viewed_titles = [v.title for v in viewed]

    max_views = max([(p.views or 0) for p in products], default=1) or 1
    rows = []
    for p, sim, matched in scored:
        pref = cat_pref.get(p.category_id, 0.0)
        heat = (p.views or 0) / max_views
        total = 0.60 * sim + 0.25 * pref + 0.15 * heat
        rows.append({
            "product": p,
            "score": round(total, 4),
            "reason": reason_for(p, matched, cat_pref, viewed_titles),
            "matched": matched[:4],
        })

    # 查询为空（“猜你喜欢”场景）：直接按偏好 + 热度排
    if not scored:
        for p in products:
            pref = cat_pref.get(p.category_id, 0.0)
            heat = (p.views or 0) / max_views
            rows.append({
                "product": p,
                "score": round(0.25 * pref + 0.15 * heat, 4),
                "reason": reason_for(p, [], cat_pref, viewed_titles),
                "matched": [],
            })

    # 用户登录但检索结果不足时，用偏好补几个
    if fill and user is not None and getattr(user, "is_authenticated", False) and len(rows) < limit:
        seen = {r["product"].id for r in rows}
        for p in products:
            if p.id in seen:
                continue
            pref = cat_pref.get(p.category_id, 0.0)
            if pref <= 0:
                continue
            heat = (p.views or 0) / max_views
            rows.append({
                "product": p,
                "score": round(0.25 * pref + 0.15 * heat, 4),
                "reason": f"你常看{p.category.name}" if p.category else "猜你喜欢",
                "matched": [],
            })

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:limit], hit_terms
