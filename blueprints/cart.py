from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Behavior, CartItem, Order, Product, db

bp = Blueprint("cart", __name__)


def _count(user_id):
    return CartItem.query.filter_by(user_id=user_id).count()


def _items(user_id):
    return (CartItem.query.filter_by(user_id=user_id)
            .order_by(CartItem.created_at.desc()).all())


@bp.route("/")
@login_required
def index():
    items = _items(current_user.id)
    valid = [i for i in items if i.product and i.product.status == "onsale"
             and i.product.seller_id != current_user.id]
    total = sum(i.product.price for i in valid)
    return render_template("cart/index.html", items=items, total=total, valid=len(valid))


@bp.route("/add/<int:pid>", methods=["POST"])
@login_required
def add(pid):
    product = Product.query.get_or_404(pid)
    if product.seller_id == current_user.id:
        return jsonify({"ok": False, "message": "不能把自己发布的商品加入购物车"}), 200
    if product.status != "onsale":
        return jsonify({"ok": False, "message": "这件商品已经不能购买"}), 200

    exists = CartItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
    if not exists:
        db.session.add(CartItem(user_id=current_user.id, product_id=pid))
        db.session.commit()

    return jsonify({"ok": True, "count": _count(current_user.id),
                    "message": "已加入购物车" if not exists else "购物车里已经有这件了"})


@bp.route("/remove/<int:item_id>", methods=["POST"])
@login_required
def remove(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        return jsonify({"ok": False, "message": "无权操作"}), 403
    db.session.delete(item)
    db.session.commit()
    if request.is_json:
        return jsonify({"ok": True, "count": _count(current_user.id)})
    flash("已从购物车移除", "info")
    return redirect(url_for("cart.index"))


@bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    """支持结算全部，或只结算勾选的那几件。"""
    selected = request.form.getlist("ids")
    items = _items(current_user.id)
    if selected:
        wanted = {int(i) for i in selected if str(i).isdigit()}
        items = [i for i in items if i.id in wanted]

    if not items:
        flash("请先勾选要结算的商品", "warning")
        return redirect(url_for("cart.index"))

    created, skipped = 0, 0
    for item in items:
        p = item.product
        if not p or p.status != "onsale" or p.seller_id == current_user.id:
            skipped += 1
            db.session.delete(item)
            continue
        db.session.add(Order(buyer_id=current_user.id, seller_id=p.seller_id,
                             product_id=p.id, amount=p.price, status="pending"))
        db.session.add(Behavior(user_id=current_user.id, product_id=p.id, action="order"))
        p.status = "sold"
        db.session.delete(item)
        created += 1

    db.session.commit()
    if created:
        msg = f"已下单 {created} 件商品"
        if skipped:
            msg += f"，{skipped} 件已被买走或不可购买"
        flash(msg, "success")
    else:
        flash("这些商品已经不能购买了", "warning")
    return redirect(url_for("order.mine"))


@bp.route("/count")
@login_required
def count():
    return jsonify({"count": _count(current_user.id)})
