from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from models import Behavior, Product, db

bp = Blueprint("history", __name__)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@bp.route("/")
@login_required
def index():
    rows = (Behavior.query
            .filter_by(user_id=current_user.id, action="view")
            .order_by(Behavior.created_at.desc())
            .limit(120).all())

    now = _now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    groups = [("今天", []), ("昨天", []), ("更早", [])]
    seen_ids = set()
    entries = []
    for b in rows:
        p = db.session.get(Product, b.product_id)
        if not p:
            continue
        day = b.created_at.date()
        label = "今天" if day == today else ("昨天" if day == yesterday else "更早")
        entries.append({"p": p, "at": b.created_at, "day": label,
                        "repeat": p.id in seen_ids})
        seen_ids.add(p.id)

    for item in entries:
        dict(groups)[item["day"]].append(item)

    return render_template("history/index.html", groups=groups, total=len(entries))


@bp.route("/clear", methods=["POST"])
@login_required
def clear():
    Behavior.query.filter_by(user_id=current_user.id, action="view").delete()
    db.session.commit()
    flash("浏览记录已清空", "info")
    return redirect(url_for("history.index"))
