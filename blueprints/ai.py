from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

import ai_engine
import listing_ai
from models import Category, Product

bp = Blueprint("ai", __name__)


def _payload():
    return request.get_json(silent=True) or request.form


@bp.route("/analyze", methods=["POST"])
def analyze():
    """发布助手：类型 / 型号 / 成色 / 估价 / 建议。"""
    d = _payload()
    title = (d.get("title") or "").strip()
    description = (d.get("description") or "").strip()
    if len(title) < 2:
        return jsonify({"ok": False, "message": "先写几个字的标题"})

    cls = ai_engine.classify_product(title, description)
    cat = Category.query.filter_by(name=cls["category"]).first()
    comparables = []
    if cat:
        rows = (Product.query
                .filter(Product.category_id == cat.id, Product.status.in_(["onsale", "sold"]))
                .order_by(Product.created_at.desc()).limit(60).all())
        comparables = [{"title": p.title, "price": p.price} for p in rows]

    try:
        original = float(d.get("original_price") or 0)
    except (TypeError, ValueError):
        original = 0.0

    result = listing_ai.analyze_listing(
        title, description, original, comparables, has_image=bool(d.get("has_image"))
    )
    result["ok"] = True
    result["comparable_count"] = len(comparables)
    return jsonify(result)


@bp.route("/assistant")
def assistant():
    return render_template("ai/assistant.html")


@bp.route("/classify", methods=["POST"])
def classify():
    d = _payload()
    result = ai_engine.classify_product(d.get("title", ""), d.get("description", ""))
    return jsonify(result)


@bp.route("/price", methods=["POST"])
def price():
    d = _payload()
    result = ai_engine.suggest_price(d.get("original_price", 0), d.get("condition", "九成新"))
    return jsonify(result)


@bp.route("/copy", methods=["POST"])
def copywriting():
    d = _payload()
    text = ai_engine.generate_copy(
        d.get("title", ""), d.get("category", "其他"),
        d.get("condition", "九成新"), d.get("original_price", 0),
    )
    return jsonify({"copy": text})


@bp.route("/moderate", methods=["POST"])
def moderate():
    d = _payload()
    return jsonify(ai_engine.moderate_text(d.get("text", "")))


@bp.route("/tags", methods=["POST"])
def tags():
    d = _payload()
    return jsonify({"tags": ai_engine.extract_tags(
        d.get("title", ""), d.get("description", ""), d.get("category", ""))})


@bp.route("/chat", methods=["POST"])
def chat():
    d = _payload()
    question = d.get("question", "")
    reply = ai_engine.chatbot_reply(question)
    reply["question"] = question
    return jsonify(reply)


@bp.route("/recommend")
def recommend():
    items = ai_engine.recommend_products(current_user, limit=8)
    return jsonify({"items": [{
        "id": p.id, "title": p.title, "price": p.price,
        "condition": p.condition, "tags": p.tag_list,
    } for p in items]})
