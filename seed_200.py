# -*- coding: utf-8 -*-
"""生成 200 件演示商品（含实物照片、标题、价格、描述、标签）。

    python seed_200.py            # 追加 200 件
    python seed_200.py --reset    # 先清空商品再生成

图片来自 static/uploads/cat_*.jpg（由 fetch_images.py 抓取），
按品类循环分配；某个品类没有图时，用渐变占位图兜底。
"""
import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "_deps"))
sys.path.insert(0, os.path.join(ROOT, "campus-secondhand"))

from app import create_app  # noqa: E402
from models import Behavior, Category, Product, User, db  # noqa: E402

UPLOADS = os.path.join(ROOT, "campus-secondhand", "static", "uploads")

# 每个品类：品牌/型号池、品类词、价格带、成色倾向
CATALOG = {
    "数码电子": [
        ("Apple", "iPhone 13 128G", 2200, 3200), ("Apple", "iPad Air 5 64G", 2400, 3200),
        ("Apple", "MacBook Air M1", 3800, 5200), ("小米", "Redmi 蓝牙耳机", 60, 220),
        ("罗技", "机械键盘 87 键", 120, 320), ("罗技", "静音鼠标 M590", 45, 130),
        ("索尼", "头戴式耳机", 200, 700), ("联想", "24 寸显示器", 400, 900),
        ("Anker", "充电宝 20000mAh", 60, 140), ("华为", "智能手表", 300, 900),
    ],
    "教材书籍": [
        ("同济版", "高等数学 第七版 上册", 10, 35), ("同济版", "线性代数 附习题册", 8, 28),
        ("高教版", "概率论与数理统计", 10, 30), ("外研社", "大学英语四级真题", 15, 40),
        ("机械工业版", "数据结构 严蔚敏", 15, 45), ("人邮版", "计算机网络 第七版", 18, 50),
        ("清华版", "操作系统 概念与实现", 20, 55), ("中信出版", "《人类简史》精装", 20, 55),
        ("作家出版社", "《活着》余华", 8, 25), ("外研社", "雅思写作真经", 20, 60),
    ],
    "生活用品": [
        ("飞利浦", "护眼台灯 三档调光", 25, 80), ("苏泊尔", "迷你电煮锅 1.2L", 35, 100),
        ("宜家", "折叠收纳箱 大号", 15, 55), ("无印良品", "记忆棉枕头", 25, 75),
        ("小米", "静音小风扇", 20, 60), ("膳魔师", "保温水壶 500ml", 20, 65),
        ("名创优品", "衣架 20 个装", 8, 25), ("公牛", "插排 五位", 15, 45),
        ("宿舍款", "床帘 遮光款", 30, 90), ("宜家", "桌面置物架", 20, 60),
    ],
    "运动户外": [
        ("斯伯丁", "篮球 7 号", 50, 180), ("李宁", "足球 5 号", 45, 160),
        ("尤尼克斯", "羽毛球拍 双拍", 40, 150), ("迪卡侬", "哑铃 5kg 一对", 40, 120),
        ("迪卡侬", "瑜伽垫 加厚", 25, 80), ("耐克", "跑鞋 42 码", 80, 350),
        ("捷安特", "通勤自行车", 200, 650), ("探路者", "登山杖 一对", 30, 90),
        ("李宁", "跳绳 计数款", 10, 35), ("迪卡侬", "护膝 一对", 15, 50),
    ],
    "服饰美妆": [
        ("北面", "羽绒服 男款 L", 120, 500), ("优衣库", "卫衣 宽松 M", 40, 160),
        ("回力", "帆布鞋 42 码", 35, 150), ("小众设计", "单肩包 沐格顿", 60, 220),
        ("小米", "双肩包 15 寸", 50, 200), ("无印良品", "羊绒围巾", 30, 120),
        ("MLB", "棒球帽", 15, 60), ("雷朋", "方框墨镜", 25, 90),
        ("ZARA", "连衣裙 M 码", 45, 180), ("mac", "口红 全新未拆", 40, 160),
    ],
    "其他": [
        ("马利", "水彩颜料 24 色", 20, 70), ("恩雅", "尤克里里 23 寸", 80, 260),
        ("桌游社", "狼人杀 桌游", 25, 80), ("多肉坊", "多肉盆栽 含盆", 10, 40),
        ("得力", "相框 六寸", 8, 30), ("达达里奥", "吉他变调夹", 10, 30),
        ("晨光", "手账本 套装", 15, 55), ("拼图社", "拼图 1000 片", 15, 50),
        ("手绘社", "台历 手绘款", 8, 25), ("晨光", "收纳笔袋", 6, 20),
    ],
}

LOOK = {"全新": "全新未拆封", "九成新": "几乎无使用痕迹", "八成新": "有轻微使用痕迹",
        "七成新": "有正常使用痕迹", "有瑕疵": "有小瑕疵"}
NOTE = {"全新": "没有笔记", "九成新": "笔记很少", "八成新": "重点章节有标注",
        "七成新": "有较多标注", "有瑕疵": "有划线"}


DESCS = {
    "数码电子": [
        "自用{months}个月，功能全部正常，无维修记录，配件齐全。",
        "外观{look}，屏幕无划痕，电池健康良好，支持当面验机。",
        "买来用得不多，{look}，附原装充电器和包装盒。",
    ],
    "教材书籍": [
        "书本{look}，笔记{note}，没有缺页，重点章节有标记。",
        "上学期用过，{look}，可以直接跟课。",
        "买重了，几乎没翻，{look}。",
    ],
    "生活用品": [
        "用了一学期，{look}，已清洁消毒。",
        "宿舍搬空转手，{look}，功能完好。",
        "买多了闲置，{look}，包装还在。",
    ],
    "运动户外": [
        "用了{months}个月，{look}，性能正常。",
        "买来想锻炼结果吃灰，{look}。",
        "毕业清仓，{look}，功能正常。",
    ],
    "服饰美妆": [
        "只穿过一两次，{look}，无污渍无破损。",
        "尺码不合适转手，{look}，可看细节图。",
        "衣柜清仓，{look}，洗过一次。",
    ],
    "其他": [
        "闲置转手，{look}，用得很少。",
        "兴趣过去就闲置了，{look}，便宜出。",
        "朋友送的用不上，{look}。",
    ],
}

SELLERS = [
    ("wangyu", "王宇", "wangyu@campus.edu", "二年级"),
    ("chenxi", "陈曦", "chenxi@campus.edu", "三年级"),
    ("linmo", "林默", "linmo@campus.edu", "一年级"),
]


def ensure_sellers():
    users = []
    for sid, name, email, _grade in SELLERS:
        u = User.query.filter_by(student_id=sid).first()
        if not u:
            u = User(student_id=sid, nickname=name, email=email, school="示范大学")
            u.set_password("123456")
            db.session.add(u)
        users.append(u)
    db.session.commit()
    return users



def variant(src_name, idx, rng):
    """从品类照片裁一个不同区域 + 轻微调色，生成唯一的一张。"""
    from PIL import ImageEnhance
    src = os.path.join(UPLOADS, src_name)
    try:
        img = Image.open(src).convert("RGB")
    except Exception:
        return src_name
    w, h = img.size
    ratio = rng.uniform(0.68, 0.95)
    cw, ch = int(w * ratio), int(h * ratio)
    x = rng.randint(0, max(0, w - cw))
    y = rng.randint(0, max(0, h - ch))
    img = img.crop((x, y, x + cw, y + ch)).resize((800, 800), Image.LANCZOS)
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.94, 1.06))
    img = ImageEnhance.Color(img).enhance(rng.uniform(0.92, 1.08))
    name = f"v_{idx:03d}.jpg"
    img.save(os.path.join(UPLOADS, name), "JPEG", quality=82)
    return name


def product_card(cat, title, cond, idx):
    """生成与商品一致的展示图（渐变底 + 品类字 + 品名 + 成色）。"""
    from PIL import ImageFont
    themes = {
        "数码电子": ((238, 242, 252), (208, 219, 240), "数"),
        "教材书籍": ((246, 241, 232), (226, 214, 194), "书"),
        "生活用品": ((238, 244, 240), (206, 222, 212), "居"),
        "运动户外": ((242, 243, 232), (216, 220, 196), "动"),
        "服饰美妆": ((249, 238, 240), (232, 208, 212), "衣"),
        "其他": ((241, 239, 246), (215, 210, 228), "杂"),
    }
    c1, c2, glyph = themes.get(cat, ((240, 240, 240), (220, 220, 220), "物"))
    img = Image.new("RGB", (800, 800), c1)
    d = ImageDraw.Draw(img)
    for y in range(800):
        k = y / 800
        d.line([(0, y), (800, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(c1, c2)))
    # 柔光圆
    d.ellipse([160, 150, 640, 630], fill=tuple(min(255, c + 14) for c in c1))
    try:
        f_big = ImageFont.truetype("C:/Windows/Fonts/simsun.ttc", 300)
        f_small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 34)
        f_tag = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
    except Exception:
        f_big = f_small = f_tag = None
    if f_big:
        w = d.textlength(glyph, font=f_big)
        d.text(((800 - w) / 2, 210), glyph, font=f_big, fill=tuple(int(c * 0.62) for c in c2))
        name = title if len(title) <= 16 else title[:15] + "…"
        w2 = d.textlength(name, font=f_small)
        d.text(((800 - w2) / 2, 660), name, font=f_small, fill=(70, 76, 86))
        w3 = d.textlength(cond, font=f_tag)
        d.text(((800 - w3) / 2, 712), cond, font=f_tag, fill=(120, 128, 140))
    name = f"p_{idx:03d}.jpg"
    img.save(os.path.join(UPLOADS, name), "JPEG", quality=84)
    return name

def images_by_cat():
    pool = {}
    for f in os.listdir(UPLOADS):
        if f.startswith("cat_") and f.endswith(".jpg"):
            cat = f.split("_")[1]
            pool.setdefault(cat, []).append(f)
    for k in pool:
        pool[k].sort()
    return pool


def placeholder(cat, idx):
    """没有照片时的兜底：柔光渐变 + 品类字。"""
    colors = {"数码电子": (232, 238, 250), "教材书籍": (243, 238, 228), "生活用品": (236, 243, 238),
              "运动户外": (240, 240, 232), "服饰美妆": (247, 236, 238), "其他": (240, 238, 244)}
    base = colors.get(cat, (238, 238, 238))
    img = Image.new("RGB", (800, 800), base)
    d = ImageDraw.Draw(img)
    for i in range(800):
        k = i / 800
        d.line([(0, i), (800, i)], fill=tuple(int(c * (0.94 + 0.12 * k)) for c in base))
    name = f"ph_{cat}_{idx}.jpg"
    img.save(os.path.join(UPLOADS, name), "JPEG", quality=80)
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--count", type=int, default=200)
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        if args.reset:
            Behavior.query.delete()
            Product.query.delete()
            db.session.commit()

        extra = ensure_sellers()
        sellers = extra + [User.query.filter_by(student_id="zhangsan").first(),
                           User.query.filter_by(student_id="lisi").first()]
        sellers = [s for s in sellers if s]
        cats = {c.name: c for c in Category.query.all()}
        pool = images_by_cat()

        rng = random.Random(20261031)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        made = 0
        per_cat = args.count // len(CATALOG) + 1

        for cat_name, cfg in CATALOG.items():
            cat = cats.get(cat_name)
            if not cat:
                continue
            imgs = pool.get({"数码电子": "digital", "教材书籍": "books", "生活用品": "life",
                             "运动户外": "sports", "服饰美妆": "fashion",
                             "其他": "other"}[cat_name], [])
            for i in range(per_cat):
                if made >= args.count:
                    break
                brand, kind, lo, hi = cfg[i % len(cfg)]
                cond = ["全新", "九成新", "九成新", "八成新", "八成新", "七成新"][i % 6]
                original = rng.randint(lo, hi) * 2 + 20
                price = max(5, int(original * {"全新": .82, "九成新": .68, "八成新": .54,
                                               "七成新": .40, "有瑕疵": .25}[cond]))
                title = f"{brand} {kind} {cond}" if rng.random() < 0.5 else f"{cond} {brand} {kind}"
                desc = rng.choice(DESCS[cat_name]).format(months=rng.randint(1, 18),
                                                      look=LOOK[cond], note=NOTE[cond])
                desc += rng.choice([" 支持校内当面交易。", " 可小刀，非诚勿扰。", " 有意私信，看到秒回。",
                                    " 图书馆门口自提优先。", " 送小配件，先到先得。"])
                image = product_card(cat_name, f"{brand} {kind}", cond, made)

                p = Product(
                    title=title, description=desc, price=float(price),
                    original_price=float(original), condition=cond,
                    image=image, category_id=cat.id,
                    seller_id=sellers[i % len(sellers)].id,
                    ai_tags=",".join([cat_name, cond, brand]),
                    campus=rng.choice([n for n in __import__('campus').CAMPUSES if n != '示范大学']),
                    views=rng.randint(3, 420),
                    status="sold" if made % 25 == 7 else "onsale",
                    created_at=now - timedelta(days=rng.randint(0, 30),
                                               hours=rng.randint(0, 23)),
                )
                db.session.add(p)
                made += 1
            db.session.commit()

        print(f"✅ 已生成 {made} 件商品")
        print(f"   在售 {Product.query.filter_by(status='onsale').count()} 件 · "
              f"商品总数 {Product.query.count()}")
        imgs_used = {p.image for p in Product.query.all()}
        print(f"   使用图片 {len(imgs_used)} 张（static/uploads）")


if __name__ == "__main__":
    main()
