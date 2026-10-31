# -*- coding: utf-8 -*-
"""按「十组 × 四子类」扩充商品库，让每个子类都有货。

用法：
    python seed_catalog.py            # 补充缺失的子类商品
    python seed_catalog.py --reset    # 清空后重建（保留用户）
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

# 子类 -> (标题模板, 原价基准, 内部映射分类)
ITEMS = {
    "女装": [("优衣库 摇粒绒外套", 399), ("ZARA 针织开衫", 259), ("学院风 JK 制服", 189),
             ("森马 卫衣裙", 219), ("优衣库 高领打底衫", 129)],
    "男装": [("优衣库 轻型羽绒服", 599), ("JackJones 卫衣", 329), ("李宁 运动短袖", 149),
             ("海澜之家 衬衫", 259), ("优衣库 摇粒绒夹克", 399)],
    "内衣": [("蕉内 纯棉内裤三件", 99), ("优衣库 HEATTECH 打底", 129), ("ubras 无痕内衣", 179)],
    "汉服": [("明制 马面裙", 299), ("宋制 对襟襦裙", 359), ("改良 汉服外套", 259)],
    "配饰": [("MLB 棒球帽", 269), ("优衣库 羊毛围巾", 199), ("雷朋 方框墨镜", 799), ("简约 皮带", 129)],
    "家电": [("小米 台灯 Pro", 179), ("美的 电热水壶", 129), ("飞利浦 电动牙刷", 299),
             ("小熊 电煮锅", 159), ("奥克斯 小风扇", 89)],
    "手机": [("Apple iPhone 13 128G", 5999), ("小米 13 256G", 4299), ("华为 P50 128G", 4488),
             ("Redmi K60 256G", 2599)],
    "通信": [("小米 Redmi 蓝牙耳机", 299), ("华为 FreeBuds 5i", 599), ("绿联 Type-C 数据线", 39)],
    "数码": [("Apple iPad Air 5 64G", 4399), ("索尼 A6400 相机", 5999), ("Apple Watch SE", 1999),
             ("小米 充电宝 20000mAh", 129)],
    "电脑": [("Apple MacBook Air M1", 7999), ("联想 小新 Pro 14", 5499), ("戴尔 灵越 15", 4999)],
    "配件": [("罗技 机械键盘 87 键", 499), ("罗技 静音鼠标 M590", 199), ("联想 24 寸显示器", 899),
             ("绿联 扩展坞", 159)],
    "办公": [("宜家 办公椅", 499), ("桌面 收纳架", 129), ("得力 文件夹", 29)],
    "文具": [("斑马 中性笔十支", 59), ("国誉 手账本", 49), ("百乐 钢笔", 189), ("杂牌 笔袋", 25)],
    "家具": [("宜家 书架", 399), ("实木 电脑桌", 599), ("宜家 置物架", 259)],
    "家装": [("宿舍 遮光床帘", 129), ("落地 衣架", 189), ("LED 灯带 5 米", 49)],
    "家居": [("无印良品 记忆棉枕头", 299), ("膳魔师 保温水壶 500ml", 259), ("纯棉 四件套", 399)],
    "厨具": [("苏泊尔 不粘锅", 199), ("双立人 菜刀", 299), ("小熊 电煮锅", 159)],
    "女鞋": [("匡威 帆布鞋 37 码", 399), ("耐克 Air Force 1 36 码", 699), ("百丽 小白鞋", 329)],
    "男鞋": [("匡威 帆布鞋 42 码", 399), ("阿迪达斯 板鞋 43 码", 599), ("李宁 跑鞋 41 码", 429)],
    "运动": [("斯伯丁 篮球 7 号", 299), ("李宁 羽毛球拍", 259), ("耐克 跑鞋 42 码", 699),
             ("迪卡侬 瑜伽垫 加厚", 199), ("迪卡侬 哑铃 一对", 159)],
    "户外": [("捷安特 通勤自行车", 1299), ("迪卡侬 登山杖", 129), ("探路者 帐篷", 599)],
    "食品": [("三只松鼠 零食大礼包", 129), ("良品铺子 坚果礼盒", 99), ("速食 螺蛳粉五包", 59)],
    "鲜花": [("昆明 玫瑰花束", 129), ("永生花 礼盒", 199)],
    "酒水": [("RIO 微醺 六瓶", 99), ("张裕 干红", 159)],
    "健康": [("欧姆龙 电子血压计", 299), ("迪卡侬 护膝 一对", 199), ("诺特兰德 蛋白粉", 259)],
    "汽车": [("车载 手机支架", 39), ("米其林 充气泵", 199), ("汽车 遮阳挡", 69)],
    "珠宝": [("施华洛世奇 项链", 799), ("银饰 手链", 259)],
    "文玩": [("星月菩提 手串", 199), ("文玩 核桃 一对", 129)],
    "箱包": [("新秀丽 双肩包", 499), ("小众设计 单肩包 沐格", 259), ("小米 行李箱 20 寸", 399)],
    "美妆": [("YSL 口红 方管", 329), ("雅诗兰黛 小棕瓶 50ml", 690), ("兰蔻 粉底液", 459)],
    "个护": [("戴森 吹风机", 2999), ("飞科 剃须刀", 199), ("植观 氨基酸洗发水", 79)],
    "娱乐": [("桌游社 狼人杀 桌游", 89), ("拼图社 拼图 1000 片", 129), ("尤克里里 23 寸", 399)],
    "图书": [("同济版 高等数学 第七版 上册", 49), ("人邮版 计算机网络 第七版", 59),
             ("清华版 操作系统 概念与实现", 45), ("外研社 雅思写作真题", 69),
             ("马利 水彩颜料 24 色", 134)],
    "母婴": [("贝亲 奶瓶 240ml", 129), ("好孩子 婴儿推车", 899)],
    "童装": [("巴拉巴拉 儿童外套", 199), ("安奈儿 儿童卫衣", 159)],
    "玩具": [("乐高 城市系列", 499), ("磁力片 100 片", 129)],
    "宠物": [("猫咪 自动喂食器", 299), ("宠物 航空箱", 199)],
    "工业品": [("博世 电钻", 599), ("世达 工具套装", 399)],
    "商业": [("收银 扫码枪", 199), ("店铺 展示架", 259)],
    "农业": [("园艺 工具箱", 129), ("小型 喷灌设备", 199)],
    "定制": [("定制 班服 卫衣", 99), ("定制 钥匙扣 一批", 49)],
}

CONDS = ["全新", "九成新", "八成新", "七成新", "有瑕疵"]
COND_RATE = {"全新": 0.85, "九成新": 0.70, "八成新": 0.55, "七成新": 0.40, "有瑕疵": 0.25}
DESC = {
    "default": "自用闲置，功能正常，外观见图。校内可当面交易，支持验货后再付款。",
    "教材": "上课用过一学期，无笔记涂画，重点章节有少量划线，不影响阅读。",
    "数码": "买来用了半年左右，一直戴壳使用，无磕碰，原装配件齐全。",
}


def pick_image(sub, files):
    """优先用按子类抓的图 p3_<子类>_*.jpg。"""
    import re as _re
    tag = _re.sub(r"[^\w]", "", sub)[:14]
    hits = [f for f in files if f.startswith(f"p3_{tag}_")]
    if not hits:
        hits = [f for f in files if sub in f]
    return random.choice(hits) if hits else (random.choice(files) if files else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="清空已有商品后重建")
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        uploads = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
        files = ([f for f in os.listdir(uploads)
                  if (f.startswith("p3_") or f.startswith("p2_")) and f.endswith(".jpg")]
                 if os.path.isdir(uploads) else [])

        if args.reset:
            Product.query.delete()
            db.session.commit()
            print("已清空商品")

        sellers = User.query.filter_by(is_admin=False).all() or User.query.all()
        cats = {c.name: c for c in Category.query.all()}
        need_cat = {"服饰美妆": "服饰美妆", "数码电子": "数码电子", "教材书籍": "教材书籍",
                    "生活用品": "生活用品", "运动户外": "运动户外", "其他": "其他"}
        for name, c in need_cat.items():
            if name not in cats:
                cats[name] = Category(name=name, icon="📦", sort=99)
                db.session.add(cats[name])
        db.session.commit()

        camps = [k for k in campus_mod.CAMPUSES if k != "示范大学"]
        rng = random.Random(20261101)
        existing = {(p.title or "") for p in Product.query.all()}
        added = 0

        for g in GROUPS:
            for sub_name, cat_names, _ in g["subs"]:
                inner = [c.strip() for c in cat_names.split()] if isinstance(cat_names, str) else list(cat_names)
                items = ITEMS.get(sub_name, [])
                for title, base in items:
                    for cond in ("九成新", "八成新"):
                        full = f"{cond} {title}"
                        if full in existing:
                            continue
                        price = int(base * COND_RATE[cond] * rng.uniform(0.9, 1.1))
                        original = base
                        cat = cats.get(inner[0] if inner else "其他") or cats["其他"]
                        desc = DESC["教材"] if "教材" in inner or sub_name == "图书" else (
                            DESC["数码"] if "数码" in inner else DESC["default"])
                        db.session.add(Product(
                            title=full,
                            description=desc,
                            price=price,
                            original_price=original,
                            condition=cond,
                            category_id=cat.id,
                            seller_id=rng.choice(sellers).id,
                            campus=rng.choice(camps),
                            image=pick_image(sub_name, files),
                            status="onsale",
                            views=rng.randint(20, 600),
                            taxo_sub=sub_name,
                        ))
                        existing.add(full)
                        added += 1
        db.session.commit()
        print(f"新增 {added} 件商品，当前在售 {Product.query.filter_by(status='onsale').count()} 件")


if __name__ == "__main__":
    main()
