from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user
from sqlalchemy import or_

import ai_engine
from config import Config
from models import Category, Product

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    cat_id = request.args.get("cat", type=int)
    keyword = (request.args.get("q") or "").strip()
    per_page = Config.PER_PAGE

    if keyword:
        query = Product.query.filter(
            Product.status == "onsale",
            or_(Product.title.contains(keyword), Product.description.contains(keyword)),
        )
        if cat_id:
            query = query.filter(Product.category_id == cat_id)
        pages = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        products = pages.items
        title = f"搜索「{keyword}」"
    elif cat_id:
        pages = (Product.query.filter_by(status="onsale", category_id=cat_id)
                 .order_by(Product.created_at.desc())
                 .paginate(page=page, per_page=per_page, error_out=False))
        products = pages.items
        cat = Category.query.get(cat_id)
        title = f"分类 · {cat.name if cat else ''}"
    else:
        recommended = ai_engine.recommend_products(current_user, limit=per_page)
        pages = None
        products = recommended
        title = "为你推荐" if current_user.is_authenticated else "热门商品"

    hot = (Product.query.filter_by(status="onsale").order_by(Product.views.desc()).limit(5).all()
           if not keyword else [])

    return render_template(
        "index.html", products=products, pages=pages, title=title,
        active_cat=cat_id, keyword=keyword, hot=hot,
    )


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "campus-secondhand", "version": "1.0.0"})
