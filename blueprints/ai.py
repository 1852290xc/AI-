from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

import ai_engine

bp = Blueprint("ai", __name__)


def _payload():
    return request.get_json(silent=True) or request.form


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
