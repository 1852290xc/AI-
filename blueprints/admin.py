from datetime import datetime, timedelta, timezone

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required

from models import Category, Order, Product, User, db

bp = Blueprint("admin", __name__)


@bp.before_request
@login_required
def guard():
    """后台守卫：非管理员直接踢回首页。"""
    if not current_user.is_admin:
        abort(403)


@bp.route("/")
def dashboard():
    today = datetime.now(timezone.utc).replace(tzinfo=None).replace(hour=0, minute=0, second=0, microsecond=0)
    stats = {
        "users": User.query.count(),
        "products": Product.query.count(),
        "orders": Order.query.count(),
        "today": Product.query.filter(Product.created_at >= today).count(),
        "onsale": Product.query.filter_by(status="onsale").count(),
        "sold": Order.query.filter_by(status="done").count(),
    }
    recent = Product.query.order_by(Product.created_at.desc()).limit(8).all()
    return render_template("admin/dashboard.html", stats=stats, recent=recent)


@bp.route("/products")
def products():
    status = request.args.get("status", "")
    query = Product.query
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", items=items, status=status)


@bp.route("/product/<int:pid>/<string:action>", methods=["POST"])
def product_action(pid, action):
    product = Product.query.get_or_404(pid)
    if action == "online":
        product.status = "onsale"
        flash("已上架", "success")
    elif action == "off":
        product.status = "off"
        flash("已下架", "warning")
    elif action == "delete":
        db.session.delete(product)
        flash("已删除", "info")
    else:
        flash("未知操作", "danger")
    db.session.commit()
    return redirect(url_for("admin.products"))


@bp.route("/users")
def users():
    items = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", items=items)


@bp.route("/user/<int:uid>/<string:action>", methods=["POST"])
def user_action(uid, action):
    user = User.query.get_or_404(uid)
    if user.id == current_user.id:
        flash("不能操作自己的账号", "warning")
        return redirect(url_for("admin.users"))

    if action == "ban":
        user.banned = True
        flash(f"已封禁 {user.nickname}", "warning")
    elif action == "unban":
        user.banned = False
        flash(f"已解封 {user.nickname}", "success")
    elif action == "promote":
        user.is_admin = not user.is_admin
        flash("管理员权限已切换", "success")
    else:
        flash("未知操作", "danger")
    db.session.commit()
    return redirect(url_for("admin.users"))


@bp.route("/categories", methods=["GET", "POST"])
def categories():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        icon = (request.form.get("icon") or "📦").strip()
        if not name:
            flash("分类名不能为空", "danger")
        elif Category.query.filter_by(name=name).first():
            flash("分类已存在", "warning")
        else:
            db.session.add(Category(name=name, icon=icon, sort=Category.query.count() + 1))
            db.session.commit()
            flash("分类已添加", "success")
        return redirect(url_for("admin.categories"))

    items = Category.query.order_by(Category.sort).all()
    return render_template("admin/categories.html", items=items)


@bp.route("/category/<int:cid>/delete", methods=["POST"])
def category_delete(cid):
    cat = Category.query.get_or_404(cid)
    if cat.products.count() > 0:
        flash("这个分类下还有商品，不能删除", "danger")
    else:
        db.session.delete(cat)
        db.session.commit()
        flash("分类已删除", "info")
    return redirect(url_for("admin.categories"))
