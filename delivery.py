# -*- coding: utf-8 -*-
"""收货方式与 AI 最优推荐。

三种方式：快递运输 / 跑腿 / 自取。
AI 按「距离 + 价格 + 物品特征 + 时效」打分，给出推荐与理由。
全是本地规则，不依赖外部服务。
"""

OPTIONS = [
    {
        "key": "express",
        "name": "快递运输",
        "icon": "📦",
        "desc": "全国可达，1–3 天",
        "cost": "¥8–15",
        "base_cost": 12,
    },
    {
        "key": "errand",
        "name": "跑腿",
        "icon": "🛵",
        "desc": "同城 1–2 小时送到",
        "cost": "¥6–20",
        "base_cost": 14,
    },
    {
        "key": "pickup",
        "name": "自取",
        "icon": "🚶",
        "desc": "约在校内/校门口面交",
        "cost": "免费",
        "base_cost": 0,
    },
]

# 物品特征对方式的影响
BULKY = ("自行车", "吉他", "尤克里里", "显示器", "台灯", "枕头", "床帘", "瑜伽垫", "哑铃", "收纳")
FRAGILE = ("显示器", "相机", "手机", "平板", "笔记本", "水壶", "颜料", "相框")
LIGHT_SMALL = ("耳机", "手表", "口红", "书", "教材", "笔", "墨镜", "变调夹", "跳绳")


def _hits(title, words):
    return sum(1 for w in words if w in title)


def recommend(distance_km=None, price=0, title="", urgency="normal"):
    """返回三种方式的评分与推荐结果。

    distance_km: 买家到卖家的距离，未知传 None
    urgency: normal / fast（急用）
    """
    d = distance_km if isinstance(distance_km, (int, float)) else None
    bulky = _hits(title, BULKY) > 0
    fragile = _hits(title, FRAGILE) > 0
    small = _hits(title, LIGHT_SMALL) > 0
    cheap = price and price <= 50

    scores, reasons = {}, {}

    # ---- 自取 ----
    s, r = 50, []
    if d is not None:
        if d <= 1:
            s += 30
            r.append("就在你附近，走几步就到")
        elif d <= 5:
            s += 18
            r.append(f"距离 {d:.1f} km，骑车十几分钟")
        elif d <= 20:
            s -= 5
            r.append(f"距离 {d:.1f} km，跑一趟有点远")
        else:
            s -= 30
            r.append(f"距离 {d:.0f} km，自取不现实")
    if bulky:
        s += 15
        r.append("体积大，自取能当场验货")
    if cheap:
        s -= 10
        r.append("单价很低，跑一趟不划算")
    scores["pickup"], reasons["pickup"] = s, r

    # ---- 跑腿 ----
    s, r = 45, []
    if d is not None:
        if d <= 5:
            s += 22
            r.append(f"同城 {d:.1f} km，跑腿 1 小时内可达")
        elif d <= 15:
            s += 8
            r.append(f"距离 {d:.1f} km，跑腿勉强能送")
        else:
            s -= 25
            r.append(f"距离 {d:.0f} km，超出同城跑腿范围")
    if urgency == "fast":
        s += 20
        r.append("你标了急用，跑腿最快")
    if fragile:
        s += 5
        r.append("易碎品，跑腿可全程手送")
    if bulky:
        s -= 10
        r.append("体积偏大，跑腿可能拒接")
    scores["errand"], reasons["errand"] = s, r

    # ---- 快递 ----
    s, r = 55, []
    if d is None or d > 20:
        s += 25
        r.append("跨城/距离远，快递是唯一现实选择" if d is None else f"距离 {d:.0f} km，快递最省心")
    elif d <= 3:
        s -= 20
        r.append("就在同校，快递反而更慢")
    elif d <= 20:
        s -= 5
        r.append("同城快递要隔天，不如自取或跑腿")
    if small:
        s += 12
        r.append("小件轻便，快递成本低")
    if bulky:
        s -= 18
        r.append("大件快递费高且易磕碰")
    if fragile:
        s -= 6
        r.append("易碎品运输有破损风险")
    if cheap:
        s += 5
        r.append("低单价小件，快递性价比高")
    scores["express"], reasons["express"] = s, r

    best = max(scores, key=scores.get)
    ranked = sorted(OPTIONS, key=lambda o: -scores[o["key"]])

    out = []
    for o in ranked:
        k = o["key"]
        out.append({
            **o,
            "score": max(0, min(100, scores[k])),
            "reason": reasons[k][:2],
            "best": k == best,
        })

    label = {"express": "快递运输", "errand": "跑腿", "pickup": "自取"}[best]
    if d is None:
        summary = f"还不知道你离卖家多远，先按「{label}」建议；开启定位后会更准。"
    elif best == "pickup":
        summary = f"你离卖家约 {d:.1f} km，建议当面自取，能验货还能省运费。"
    elif best == "errand":
        summary = f"你离卖家约 {d:.1f} km，建议叫跑腿，1 小时内能到手。"
    else:
        summary = f"你离卖家约 {d:.0f} km，建议走快递，运费可控也不用来回跑。"

    return {
        "distance_km": round(d, 1) if d is not None else None,
        "best": best,
        "best_name": label,
        "summary": summary,
        "options": out,
    }
