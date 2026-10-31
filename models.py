from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def utcnow():
    """朴素 UTC 时间（SQLite 里存无时区时间戳）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class User(UserMixin, TimestampMixin, db.Model):
    """学生 / 管理员账号。"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(32), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    school = db.Column(db.String(64), default="示范大学")
    credit = db.Column(db.Integer, default=100)          # 信用分
    is_admin = db.Column(db.Boolean, default=False)
    banned = db.Column(db.Boolean, default=False)
    lat = db.Column(db.Float)          # 最近一次授权定位的纬度
    lng = db.Column(db.Float)          # 最近一次授权定位的经度

    products = db.relationship("Product", backref="seller", lazy="dynamic")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def avatar_text(self):
        return self.nickname[:1] if self.nickname else "?"

    def __repr__(self):
        return f"<User {self.student_id}>"


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    icon = db.Column(db.String(8), default="📦")
    sort = db.Column(db.Integer, default=0)

    products = db.relationship("Product", backref="category", lazy="dynamic")


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False, default=0)
    original_price = db.Column(db.Float, default=0)
    condition = db.Column(db.String(16), default="九成新")
    image = db.Column(db.String(255), default="")
    ai_tags = db.Column(db.String(255), default="")       # 逗号分隔
    campus = db.Column(db.String(64))                     # 交易校区（默认取卖家学校）
    status = db.Column(db.String(16), default="onsale")   # onsale / sold / off / pending
    views = db.Column(db.Integer, default=0)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    favorites = db.relationship("Favorite", backref="product", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def tag_list(self):
        return [t for t in (self.ai_tags or "").split(",") if t]

    @property
    def cover(self):
        return self.image or ""

    @property
    def discount_text(self):
        if self.original_price and self.original_price > 0:
            return f"{self.price / self.original_price * 10:.1f} 折"
        return ""


class Favorite(TimestampMixin, db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_user_product"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)


class Order(TimestampMixin, db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(16), default="pending")   # pending / done / canceled

    buyer = db.relationship("User", foreign_keys=[buyer_id])
    seller = db.relationship("User", foreign_keys=[seller_id])
    product = db.relationship("Product")


class Message(TimestampMixin, db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])


class Behavior(TimestampMixin, db.Model):
    """浏览 / 收藏 / 下单行为，喂给推荐算法。"""

    __tablename__ = "behaviors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    action = db.Column(db.String(16), default="view")      # view / fav / order

    product = db.relationship("Product")

class CartItem(TimestampMixin, db.Model):
    """购物车：一人一件商品只能加一次。"""

    __tablename__ = "cart_items"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    product = db.relationship("Product")


class SearchHistory(TimestampMixin, db.Model):
    """搜索记录：同一关键词只留一条，重复搜索累加次数并置顶。"""

    __tablename__ = "search_history"
    __table_args__ = (db.UniqueConstraint("user_id", "keyword", name="uq_user_keyword"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    keyword = db.Column(db.String(64), nullable=False)
    times = db.Column(db.Integer, default=1)
