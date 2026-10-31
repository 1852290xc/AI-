import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from models import Behavior, Favorite, Order, Product, User, db

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$")
STUDENT_RE = re.compile(r"^[A-Za-z0-9]{4,20}$")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        student_id = (request.form.get("student_id") or "").strip()
        nickname = (request.form.get("nickname") or "").strip()
        school = (request.form.get("school") or "").strip() or "示范大学"
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        errors = []
        if not STUDENT_RE.match(student_id):
            errors.append("学号需为 4–20 位字母或数字")
        if len(nickname) < 2:
            errors.append("昵称至少 2 个字")
        if not EMAIL_RE.match(email):
            errors.append("邮箱格式不正确")
        if len(password) < 6:
            errors.append("密码至少 6 位")
        if password != confirm:
            errors.append("两次输入的密码不一致")
        if User.query.filter_by(student_id=student_id).first():
            errors.append("这个学号已经注册过了")
        if User.query.filter_by(email=email).first():
            errors.append("这个邮箱已经注册过了")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", form=request.form)

        user = User(student_id=student_id, nickname=nickname, email=email, school=school)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f"欢迎加入，{user.nickname}！", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        account = (request.form.get("account") or "").strip()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter(
            (User.student_id == account) | (User.email == account.lower())
        ).first()

        if not user or not user.check_password(password):
            flash("账号或密码不正确", "danger")
            return render_template("auth/login.html", form=request.form)
        if user.banned:
            flash("该账号已被封禁，请联系管理员", "danger")
            return render_template("auth/login.html", form=request.form)

        login_user(user, remember=remember)
        flash(f"欢迎回来，{user.nickname}", "success")
        nxt = request.args.get("next")
        if nxt and nxt.startswith("/"):
            return redirect(nxt)
        return redirect(url_for("main.index"))

    return render_template("auth/login.html", form={})


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录", "info")
    return redirect(url_for("main.index"))


@bp.route("/profile")
@login_required
def profile():
    my_products = Product.query.filter_by(seller_id=current_user.id).count()
    bought = Order.query.filter_by(buyer_id=current_user.id).count()
    sold = Order.query.filter_by(seller_id=current_user.id).count()
    favs = Favorite.query.filter_by(user_id=current_user.id).count()
    views = Behavior.query.filter_by(user_id=current_user.id, action="view").count()
    return render_template(
        "auth/profile.html",
        stats={"products": my_products, "bought": bought, "sold": sold, "favorites": favs, "views": views},
        recent=Product.query.filter_by(seller_id=current_user.id).order_by(Product.created_at.desc()).limit(4).all(),
    )


@bp.route("/profile/edit", methods=["POST"])
@login_required
def profile_edit():
    nickname = (request.form.get("nickname") or "").strip()
    school = (request.form.get("school") or "").strip()
    email = (request.form.get("email") or "").strip().lower()

    if len(nickname) < 2:
        flash("昵称至少 2 个字", "danger")
        return redirect(url_for("auth.profile"))
    if email and not EMAIL_RE.match(email):
        flash("邮箱格式不正确", "danger")
        return redirect(url_for("auth.profile"))
    exists = User.query.filter(User.email == email, User.id != current_user.id).first()
    if exists:
        flash("这个邮箱已被占用", "danger")
        return redirect(url_for("auth.profile"))

    current_user.nickname = nickname
    current_user.school = school or current_user.school
    if email:
        current_user.email = email
    db.session.commit()
    flash("资料已更新", "success")
    return redirect(url_for("auth.profile"))
