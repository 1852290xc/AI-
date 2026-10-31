# -*- coding: utf-8 -*-
"""按「市场价 × 成色系数」生成商品，保证价格与成色、标签、描述一致。

规则：
    全新   = 市场价 × 0.80
    九成新 = 市场价 × 0.68
    八成新 = 市场价 × 0.56
    七成新 = 市场价 × 0.45
    有瑕疵 = 市场价 × 0.30

原价字段填真实市场价，所以详情页折扣 = 成交价 / 市场价。

    python seed_catalog.py --reset     # 清空商品后按规则重建
    python seed_catalog.py             # 只补缺失的
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402
from models import Category, Product, User, db  # noqa: E402
import campus as campus_mod  # noqa: E402
from taxonomy import GROUPS  # noqa: E402

# 子类 -> [(商品名, 市场价)]
ITEMS = {
    "女装": [("优衣库 摇粒绒外套", 399), ("ZARA 针织开衫", 299), ("学院风 JK 制服", 259),
             ("森马 连帽卫衣裙", 239), ("优衣库 高领打底衫", 149)],
    "男装": [("优衣库 轻型羽绒服", 599), ("JackJones 卫衣", 359), ("李宁 运动短袖", 159),
             ("海澜之家 长袖衬衫", 279), ("优衣库 摇粒绒夹克", 399)],
    "汉服": [("明制 马面裙", 329), ("宋制 对襟襦裙", 399), ("改良 汉服外套", 289)],
    "配饰": [("MLB 棒球帽", 299), ("优衣库 羊毛围巾", 219), ("雷朋 方框墨镜", 899), ("头层牛皮 腰带", 159)],
    "家电": [("小米 台灯 Pro", 199), ("美的 电热水壶", 149), ("飞利浦 电动牙刷", 329),
             ("小熊 电煮锅", 179), ("奥克斯 落地小风扇", 99)],
    "手机": [("Apple iPhone 13 128G", 5999), ("小米 13 256G", 4299), ("华为 P50 128G", 4488),
             ("Redmi K60 256G", 2599)],
    "通信": [("小米 Redmi 蓝牙耳机", 299), ("华为 FreeBuds 5i", 599), ("绿联 Type-C 数据线", 49)],
    "数码": [("Apple iPad Air 5 64G", 4399), ("索尼 A6400 微单相机", 5999), ("Apple Watch SE", 1999),
             ("小米 充电宝 20000mAh", 149)],
    "电脑": [("Apple MacBook Air M1", 7999), ("联想 小新 Pro 14", 5499), ("戴尔 灵越 15", 4999)],
    "配件": [("罗技 机械键盘 87 键", 499), ("罗技 静音鼠标 M590", 199), ("联想 24 寸显示器", 899),
             ("绿联 七合一扩展坞", 169)],
    "办公": [("宜家 人体工学办公椅", 599), ("桌面 双层收纳架", 139), ("得力 A4 文件夹十个", 39)],
    "文具": [("斑马 中性笔十支装", 69), ("国誉 手账本 A5", 49), ("百乐 钢笔 78G", 199), ("帆布 笔袋", 29)],
    "家具": [("宜家 四层书架", 399), ("实木 电脑桌 120cm", 699), ("宜家 置物架", 259)],
    "家装": [("宿舍 遮光床帘", 139), ("落地 衣架", 199), ("LED 灯带 5 米", 59)],
    "家居": [("无印良品 记忆棉枕头", 299), ("膳魔师 保温水壶 500ml", 259), ("纯棉 四件套 1.5m", 399)],
    "厨具": [("苏泊尔 不粘炒锅 28cm", 199), ("双立人 菜刀", 299), ("小熊 电煮锅 1.2L", 179)],
    "女鞋": [("匡威 帆布鞋 37 码", 399), ("耐克 Air Force 1 36 码", 699), ("百丽 小白鞋 38 码", 329)],
    "男鞋": [("匡威 帆布鞋 42 码", 399), ("阿迪达斯 板鞋 43 码", 599), ("李宁 跑鞋 41 码", 429)],
    "运动": [("斯伯丁 篮球 7 号", 299), ("李宁 羽毛球拍 一对", 259), ("耐克 跑鞋 42 码", 699),
             ("迪卡侬 瑜伽垫 加厚", 199), ("迪卡侬 哑铃 一对 5kg", 159)],
    "户外": [("捷安特 通勤自行车", 1299), ("迪卡侬 登山杖 一对", 139), ("探路者 双人帐篷", 599)],
    "食品": [("三只松鼠 零食大礼包", 139), ("良品铺子 坚果礼盒", 109), ("柳州 螺蛳粉五包", 59)],
    "鲜花": [("昆明 玫瑰花束 20 支", 139), ("永生花 玻璃罩礼盒", 199)],
    "酒水": [("RIO 微醺 六瓶装", 99), ("张裕 干红葡萄酒", 159)],
    "健康": [("欧姆龙 电子血压计", 299), ("迪卡侬 护膝 一对", 199), ("诺特兰德 乳清蛋白粉", 259)],
    "汽车": [("车载 手机支架", 49), ("米其林 车载充气泵", 199), ("汽车 前挡遮阳挡", 69)],
    "珠宝": [("施华洛世奇 天鹅项链", 799), ("925 银 手链", 259)],
    "文玩": [("星月菩提 手串", 199), ("文玩 核桃 一对", 129)],
    "箱包": [("新秀丽 双肩包", 499), ("小众设计 单肩包 沐格", 259), ("小米 行李箱 20 寸", 399)],
    "美妆": [("YSL 方管口红 #1966", 329), ("雅诗兰黛 小棕瓶 50ml", 690), ("兰蔻 持妆粉底液", 459)],
    "个护": [("戴森 吹风机 HD08", 2999), ("飞科 电动剃须刀", 199), ("植观 氨基酸洗发水", 89)],
    "娱乐": [("狼人杀 桌游 全套", 89), ("拼图 1000 片 风景", 129), ("尤克里里 23 寸", 399)],
    "图书": [("同济版 高等数学 第七版 上册", 49), ("人邮版 计算机网络 第七版", 59),
             ("清华版 操作系统 概念与实现", 45), ("外研社 雅思写作真题", 69),
             ("马利 水彩颜料 24 色", 134)],
    "母婴": [("贝亲 宽口径奶瓶 240ml", 129), ("好孩子 轻便婴儿推车", 899)],
    "童装": [("巴拉巴拉 儿童外套 120cm", 199), ("安奈儿 儿童卫衣 130cm", 159)],
    "玩具": [("乐高 城市系列 60380", 499), ("磁力片 100 片装", 129)],
    "宠物": [("小佩 自动喂食器", 299), ("宠物 航空箱 中号", 199)],
    "工业品": [("博世 手电钻", 599), ("世达 46 件工具套装", 399)],
    "商业": [("收银 扫码枪", 199), ("店铺 展示架", 259)],
    "农业": [("园艺 工具五件套", 129), ("小型 喷灌设备", 199)],
    "定制": [("定制 班服卫衣", 99), ("定制 钥匙扣 一批", 59)],
}

# 成色 -> 市场价系数（全新 8 折，逐层下降）
COND_FACTOR = {"全新": 0.80, "九成新": 0.68, "八成新": 0.56, "七成新": 0.45, "有瑕疵": 0.30}

CLOTH_KW = ("服装", "外套", "卫衣", "裙", "衬衫", "短袖", "襦裙", "打底衫", "开衫", "夹克", "羽绒服")

DESC_TMPL = {
    "全新": "买重了用不上，{name}全新未拆封，包装和吊牌都在，可当面验货。",
    "九成新": "{name}买来只用过几次，成色很新，无磕碰无划痕，{extra}配件齐全。",
    "八成新": "{name}正常使用痕迹，功能完好不影响使用，{extra}介意成色慎拍。",
    "七成新": "{name}用得比较久，有明显使用痕迹但功能正常，{extra}价格已经让到位。",
    "有瑕疵": "{name}有使用瑕疵，{extra}已如实说明，介意勿拍。",
}

EXTRA = {
    "数码电子": "电池健康 90% 以上，",
    "教材书籍": "无笔记涂画，",
    "运动户外": "无破损，",
    "服饰美妆": "已清洗消毒，",
    "生活用品": "清洗干净，",
    "其他": "",
}


def sub_conditions(sub, name):
    if sub in ("图书", "文具"):
        return ["九成新", "八成新"]
    if sub in ("食品", "鲜花", "酒水"):
        return ["全新"]
    if any(k in name for k in CLOTH_KW):
        return ["九成新", "八成新", "七成新"]
    return ["全新", "九成新", "八成新"]


def pick_image(sub, name, files):
    """优先用「按商品名」抓的图，其次按子类，最后任意图。"""
    import re as _re
    tag = _re.sub(r"[^\w]", "", name)[:16]
    hits = [f for f in files if f.startswith(f"p4_{tag}_")]
    if not hits:
        sub_tag = _re.sub(r"[^\w]", "", sub)[:14]
        hits = [f for f in files if f.startswith(f"p3_{sub_tag}_")]
    if not hits:
        hits = [f for f in files if f.startswith("p2_")]
    return random.choice(hits) if hits else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        uploads = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
        files = ([f for f in os.listdir(uploads)
                  if f.endswith(".jpg") and (f.startswith("p4_") or f.startswith("p3_") or f.startswith("p2_"))]
                 if os.path.isdir(uploads) else [])

        if args.reset:
            Product.query.delete()
            db.session.commit()
            print("已清空原有商品")

        sellers = User.query.filter_by(is_admin=False).all() or User.query.all()
        cats = {c.name: c for c in Category.query.all()}
        for name in ("服饰美妆", "数码电子", "教材书籍", "生活用品", "运动户外", "其他"):
            if name not in cats:
                cats[name] = Category(name=name, icon="📦", sort=99)
                db.session.add(cats[name])
        db.session.commit()

        camps = [k for k in campus_mod.CAMPUSES if k != "示范大学"]
        rng = random.Random(20261101)
        existing = {(p.title or "") for p in Product.query.all()}
        added = 0

        variant_idx = {}
        for g in GROUPS:
            for sub_name, cat_names, _ in g["subs"]:
                inner = [c.strip() for c in cat_names.split()] if isinstance(cat_names, str) else list(cat_names)
                cat = cats.get(inner[0] if inner else "其他") or cats["其他"]
                extra = EXTRA.get(cat.name, "")
                for name, market in ITEMS.get(sub_name, []):
                    _imgs = sorted(f for f in files if f.startswith("p4_" + __import__("re").sub(r"[^\w]", "", name)[:16] + "_"))
                    for cond in sub_conditions(sub_name, name):
                        title = f"{cond} {name}"
                        if title in existing:
                            continue
                        price = max(1, int(round(market * COND_FACTOR[cond])))
                        # 同一商品的不同成色，尽量配不同的图
                        k = variant_idx.get(name, 0)
                        variant_idx[name] = k + 1
                        img = _imgs[k % len(_imgs)] if _imgs else pick_image(sub_name, name, files)
                        db.session.add(Product(
                            title=title,
                            description=DESC_TMPL[cond].format(name=name, extra=extra),
                            price=price,
                            original_price=market,
                            condition=cond,
                            category_id=cat.id,
                            seller_id=rng.choice(sellers).id,
                            campus=rng.choice(camps),
                            image=img,
                            status="onsale",
                            views=rng.randint(20, 600),
                            taxo_sub=sub_name,
                            ai_tags=f"{cat.name},{cond},{sub_name}",
                        ))
                        existing.add(title)
                        added += 1
        db.session.commit()
        print(f"新增 {added} 件，在售 {Product.query.filter_by(status='onsale').count()} 件")


if __name__ == "__main__":
    main()
