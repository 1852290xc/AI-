"""数据库初始化：建表 + 6 个分类 + 3 个账号 + 16 件演示商品 + 浏览行为。

用法：
    python init_db.py
"""
from datetime import datetime, timedelta, timezone

from app import create_app
from models import Behavior, Category, Favorite, Message, Order, Product, User, db

CATEGORIES = [
    ("数码电子", "💻"),
    ("教材书籍", "📚"),
    ("生活用品", "🛋"),
    ("运动户外", "🏀"),
    ("服饰美妆", "👕"),
    ("其他", "📦"),
]

PRODUCTS = [
    # (标题, 分类, 价格, 原价, 成色, 描述, 浏览数)
    ("九成新 iPhone 13 128G 星光色", "数码电子", 2899, 5999, "九成新",
     "自用一年半，无维修无进水，电池健康 87%，送原装充电器和保护壳。", 156),
    ("iPad Air 5 64G 深空灰 带笔", "数码电子", 2699, 4399, "九成新",
     "上网课买的，用了不到半年，屏幕无划痕，附 Apple Pencil 2。", 203),
    ("机械键盘 87 键 红轴", "数码电子", 189, 399, "八成新",
     "宿舍用过一学期，键帽无打油，送一套替换键帽。", 88),
    ("罗技 M590 静音鼠标", "数码电子", 79, 169, "九成新", "手感好，静音按键，适合图书馆用。", 64),
    ("高数（第七版）上下册 同济", "教材书籍", 25, 78, "八成新",
     "有少量铅笔笔记，无缺页，考研复习够用。", 132),
    ("考研英语真题 2020–2025", "教材书籍", 35, 89, "九成新",
     "只做了前两套，答案完整，无涂改。", 97),
    ("线性代数 附习题册", "教材书籍", 18, 45, "七成新", "书角有磨损，内页干净。", 45),
    ("《人类简史》精装", "教材书籍", 30, 68, "九成新", "读过一遍，无笔记，适合课外阅读。", 58),
    ("宿舍护眼台灯 三档调光", "生活用品", 39, 99, "八成新",
     "LED 无频闪，USB 供电，搬宿舍带不走。", 76),
    ("迷你电煮锅 1.2L", "生活用品", 45, 129, "九成新", "煮面煮粥都行，宿舍可用，已清洁。", 61),
    ("折叠收纳箱 大号两个", "生活用品", 20, 60, "八成新", "搬宿舍神器，无破损。", 33),
    ("篮球 斯伯丁 7 号", "运动户外", 89, 199, "八成新",
     "打了一学期，气足，纹路清楚。", 71),
    ("羽毛球拍 双拍套装", "运动户外", 65, 159, "九成新", "买来只用过三四次，送三个球。", 54),
    ("羽绒服 男款 L 码 黑色", "服饰美妆", 199, 699, "九成新",
     "去年冬天买的，穿过一季，无破损无污渍。", 118),
    ("帆布鞋 42 码 白色", "服饰美妆", 59, 199, "八成新", "洗过一次，鞋底磨损轻微。", 42),
    ("手绘水彩颜料套装", "其他", 35, 88, "九成新", "24 色，用了两三次，剩很多。", 29),
]


def seed_data():
    """在已有 app context 内调用。"""
    for name, icon in CATEGORIES:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name, icon=icon, sort=len(CATEGORIES)))

    db.session.commit()

    def make_user(student_id, nickname, email, password, school="示范大学", is_admin=False):
        user = User.query.filter_by(student_id=student_id).first()
        if user:
            return user
        user = User(student_id=student_id, nickname=nickname, email=email,
                    school=school, is_admin=is_admin, credit=100)
        user.set_password(password)
        db.session.add(user)
        return user

    admin = make_user("admin", "管理员", "admin@campus.edu", "admin123", is_admin=True)
    zhangsan = make_user("zhangsan", "张三", "zhangsan@campus.edu", "123456")
    lisi = make_user("lisi", "李四", "lisi@campus.edu", "123456", school="示范大学")
    db.session.commit()

    if Product.query.count() == 0:
        cat_map = {c.name: c for c in Category.query.all()}
        sellers = [zhangsan, lisi, admin]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i, (title, cat, price, original, cond, desc, views) in enumerate(PRODUCTS):
            db.session.add(Product(
                title=title, description=desc, price=price, original_price=original,
                condition=cond, category_id=cat_map[cat].id, seller_id=sellers[i % 3].id,
                ai_tags=cat, views=views, status="onsale",
                created_at=now - timedelta(days=i % 7, hours=i),
            ))
        db.session.commit()

    # 给张三制造浏览行为：数码 + 教材各看几件，推荐算法才有料
    if not Behavior.query.filter_by(user_id=zhangsan.id).first():
        liked = Product.query.filter(Product.title.contains("iPhone") |
                                     Product.title.contains("iPad") |
                                     Product.title.contains("键盘") |
                                     Product.title.contains("高数") |
                                     Product.title.contains("考研")).all()
        for p in liked:
            db.session.add(Behavior(user_id=zhangsan.id, product_id=p.id, action="view"))
        db.session.commit()

    return {"categories": Category.query.count(), "users": User.query.count(),
            "products": Product.query.count(), "behaviors": Behavior.query.count()}


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        stats = seed_data()
        print("✅ 数据库初始化完成")
        print(f"   分类 {stats['categories']} 个 · 用户 {stats['users']} 个 · "
              f"商品 {stats['products']} 件 · 行为 {stats['behaviors']} 条")
        print("   演示账号：admin/admin123　zhangsan/123456　lisi/123456")
