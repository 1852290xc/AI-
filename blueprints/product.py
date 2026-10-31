import os
import uuid

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

import ai_engine
import delivery
import inspection
import campus as campus_mod
from config import Config
from models import Behavior, Category, Favorite, Product, db

bp = Blueprint("product", __name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def save_image(file_storage):
    """安全保存上传图片，返回文件名；失败返回空串。"""
    if not file_storage or not file_storage.filename:
        return ""
    if not allowed_file(file_storage.filename):
        return ""
    safe = secure_filename(file_storage.filename)
    ext = safe.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex[:16]}.{ext}"
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    file_storage.save(os.path.join(Config.UPLOAD_FOLDER, name))
    return name


@bp.route("/publish", methods=["GET", "POST"])
@login_required
def publish():
    cats = Category.query.order_by(Category.sort).all()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        condition = request.form.get("condition") or "九成新"
        category_id = request.form.get("category_id") or ""
        try:
            price = float(request.form.get("price") or 0)
            original_price = float(request.form.get("original_price") or 0)
        except ValueError:
            flash("价格必须是数字", "danger")
            return render_template("product/publish.html", cats=cats, form=request.form)

        if len(title) < 3:
            flash("标题至少 3 个字", "danger")
            return render_template("product/publish.html", cats=cats, form=request.form)
        if price <= 0:
            flash("请填写出售价格", "danger")
            return render_template("product/publish.html", cats=cats, form=request.form)

        # 1) AI 审核（标题 + 描述）
        verdict = ai_engine.moderate_text(f"{title} {description}")
        if not verdict["passed"]:
            flash(f"发布被拦截：{verdict['message']}", "danger")
            return render_template("product/publish.html", cats=cats, form=request.form)

        # 2) 未选分类时由 AI 自动补一个
        auto_classified = False
        if category_id:
            cat = Category.query.get(int(category_id))
        else:
            result = ai_engine.classify_product(title, description)
            cat = Category.query.filter_by(name=result["category"]).first()
            auto_classified = True

        # 3) 标签
        tags = ai_engine.extract_tags(title, description, cat.name if cat else "")

        product = Product(
            title=title,
            description=description,
            price=price,
            original_price=original_price,
            condition=condition,
            image=save_image(request.files.get("image")),
            ai_tags=",".join(tags),
            category_id=cat.id if cat else None,
            seller_id=current_user.id,
            status="onsale",
        )
        db.session.add(product)
        db.session.commit()

        if auto_classified and cat:
            flash(f"发布成功！AI 已自动归类为「{cat.name}」", "success")
        else:
            flash("发布成功！", "success")
        return redirect(url_for("product.detail", pid=product.id))

    return render_template("product/publish.html", cats=cats, form={})


@bp.route("/<int:pid>")
def detail(pid):
    product = Product.query.get_or_404(pid)
    product.views = (product.views or 0) + 1
    db.session.commit()

    if current_user.is_authenticated:
        db.session.add(Behavior(user_id=current_user.id, product_id=product.id, action="view"))
        db.session.commit()

    is_fav = False
    if current_user.is_authenticated:
        is_fav = Favorite.query.filter_by(user_id=current_user.id, product_id=product.id).first() is not None

    related = (Product.query.filter(Product.category_id == product.category_id,
                                    Product.id != product.id,
                                    Product.status == "onsale")
               .order_by(Product.views.desc()).limit(4).all())

    # 收货方式：算买家到卖家的距离，交给 AI 推荐
    km = None
    school = product.campus or (product.seller.school if product.seller else "")
    lat = getattr(current_user, "lat", None) if current_user.is_authenticated else None
    lng = getattr(current_user, "lng", None) if current_user.is_authenticated else None
    if lat is None:
        lat, lng = session.get("lat"), session.get("lng")
    if lat and lng:
        spot = campus_mod.coords(school)
        if spot:
            km = campus_mod.distance_km(lat, lng, spot[0], spot[1])
    ship = delivery.recommend(km, product.price or 0, product.title or "")

    # 质检报告：查重 + 同类价格中位数
    dup = False
    if product.image:
        cur_hash = inspection.image_ai.hash_of_file(os.path.join(Config.UPLOAD_FOLDER, product.image))
        if cur_hash is not None:
            others = [x for x in Product.query.filter(Product.id != product.id, Product.image.isnot(None)).limit(300)]
            for o in others:
                h = inspection.image_ai.hash_of_file(os.path.join(Config.UPLOAD_FOLDER, o.image or ""))
                if h is not None and inspection.image_ai.similarity(cur_hash, h) >= 0.88:
                    dup = True
                    break
    prices = sorted([x.price for x in Product.query.filter_by(category_id=product.category_id, status="onsale")
                     if x.price])
    median = prices[len(prices) // 2] if prices else None
    report = inspection.build_report(product, duplicates_same=dup, price_median=median)

    return render_template("product/detail.html", p=product, is_fav=is_fav, related=related,
                           ship=ship, report=report)


@bp.route("/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def edit(pid):
    product = Product.query.get_or_404(pid)
    if product.seller_id != current_user.id and not current_user.is_admin:
        abort(403)
    cats = Category.query.order_by(Category.sort).all()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        verdict = ai_engine.moderate_text(f"{title} {description}")
        if not verdict["passed"]:
            flash(f"修改被拦截：{verdict['message']}", "danger")
            return render_template("product/edit.html", p=product, cats=cats)

        product.title = title
        product.description = description
        product.condition = request.form.get("condition") or product.condition
        try:
            product.price = float(request.form.get("price") or product.price)
            product.original_price = float(request.form.get("original_price") or product.original_price)
        except ValueError:
            flash("价格必须是数字", "danger")
            return render_template("product/edit.html", p=product, cats=cats)

        cid = request.form.get("category_id")
        if cid:
            product.category_id = int(cid)
        product.ai_tags = ",".join(ai_engine.extract_tags(title, description,
                                                          product.category.name if product.category else ""))
        img = save_image(request.files.get("image"))
        if img:
            product.image = img
        db.session.commit()
        flash("商品已更新", "success")
        return redirect(url_for("product.detail", pid=product.id))

    return render_template("product/edit.html", p=product, cats=cats)


@bp.route("/<int:pid>/delete", methods=["POST"])
@login_required
def delete(pid):
    product = Product.query.get_or_404(pid)
    if product.seller_id != current_user.id and not current_user.is_admin:
        abort(403)
    db.session.delete(product)
    db.session.commit()
    flash("商品已删除", "info")
    return redirect(url_for("product.my"))


@bp.route("/<int:pid>/off", methods=["POST"])
@login_required
def take_off(pid):
    product = Product.query.get_or_404(pid)
    if product.seller_id != current_user.id and not current_user.is_admin:
        abort(403)
    product.status = "off" if product.status == "onsale" else "onsale"
    db.session.commit()
    flash("已更新商品状态", "success")
    return redirect(url_for("product.my"))


@bp.route("/my")
@login_required
def my():
    items = (Product.query.filter_by(seller_id=current_user.id)
             .order_by(Product.created_at.desc()).all())
    return render_template("product/my.html", items=items)


@bp.route("/<int:pid>/favorite", methods=["POST"])
@login_required
def favorite(pid):
    product = Product.query.get_or_404(pid)
    fav = Favorite.query.filter_by(user_id=current_user.id, product_id=pid).first()
    if fav:
        db.session.delete(fav)
        state = False
    else:
        db.session.add(Favorite(user_id=current_user.id, product_id=pid))
        db.session.add(Behavior(user_id=current_user.id, product_id=pid, action="fav"))
        state = True
    db.session.commit()
    count = Favorite.query.filter_by(product_id=pid).count()
    return jsonify({"ok": True, "favorited": state, "count": count})
