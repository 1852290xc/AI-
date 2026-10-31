from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from models import Behavior, Order, Product, db

bp = Blueprint("order", __name__)


@bp.route("/create/<int:pid>", methods=["POST"])
@login_required
def create(pid):
    product = Product.query.get_or_404(pid)

    if product.seller_id == current_user.id:
        flash("不能购买自己发布的商品", "danger")
        return redirect(url_for("product.detail", pid=pid))
    if product.status != "onsale":
        flash("这件商品已经不能购买了", "warning")
        return redirect(url_for("product.detail", pid=pid))

    exists = Order.query.filter_by(buyer_id=current_user.id, product_id=pid).filter(
        Order.status.in_(["pending", "done"])
    ).first()
    if exists:
        flash("你已经下过单了，请到「我的订单」查看", "warning")
        return redirect(url_for("order.mine"))

    order = Order(buyer_id=current_user.id, seller_id=product.seller_id,
                  product_id=product.id, amount=product.price, status="pending")
    product.status = "sold"
    db.session.add(order)
    db.session.add(Behavior(user_id=current_user.id, product_id=pid, action="order"))
    db.session.commit()

    flash("下单成功，请联系卖家确认交易", "success")
    return redirect(url_for("order.mine"))


@bp.route("/mine")
@login_required
def mine():
    bought = (Order.query.filter_by(buyer_id=current_user.id)
              .order_by(Order.created_at.desc()).all())
    sold = (Order.query.filter_by(seller_id=current_user.id)
            .order_by(Order.created_at.desc()).all())
    return render_template("order/mine.html", bought=bought, sold=sold)


@bp.route("/<int:oid>/done", methods=["POST"])
@login_required
def done(oid):
    order = Order.query.get_or_404(oid)
    if current_user.id not in (order.buyer_id, order.seller_id):
        flash("无权操作这个订单", "danger")
        return redirect(url_for("order.mine"))
    order.status = "done"
    db.session.commit()
    flash("订单已完成，别忘了给卖家好评", "success")
    return redirect(url_for("order.mine"))


@bp.route("/<int:oid>/cancel", methods=["POST"])
@login_required
def cancel(oid):
    order = Order.query.get_or_404(oid)
    if current_user.id not in (order.buyer_id, order.seller_id):
        flash("无权操作这个订单", "danger")
        return redirect(url_for("order.mine"))
    if order.status != "pending":
        flash("只有待确认的订单可以取消", "warning")
        return redirect(url_for("order.mine"))

    order.status = "canceled"
    product = Product.query.get(order.product_id)
    if product and product.status == "sold":
        product.status = "onsale"      # 商品重新上架
    db.session.commit()
    flash("订单已取消，商品重新上架", "info")
    return redirect(url_for("order.mine"))
