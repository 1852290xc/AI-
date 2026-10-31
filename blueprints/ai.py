import os

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

import ai_engine
import image_ai
import listing_ai
from config import Config
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


@bp.route("/image-check", methods=["POST"])
def image_check():
    """查重 + AI 痕迹 + 与参考图比对。"""
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "message": "没有收到图片"}), 400
    try:
        img = image_ai.load_image(f.stream)
    except Exception:
        return jsonify({"ok": False, "message": "图片无法解析，换一张试试"}), 400

    meta = image_ai.read_meta(img)
    score, reasons = image_ai.ai_traces(img, meta)

    # 与站内图片查重（最多取 300 张，够用且够快）
    paths = []
    for p in Product.query.order_by(Product.id.desc()).limit(300).all():
        if p.image:
            paths.append((p.image, os.path.join(Config.UPLOAD_FOLDER, p.image)))
    dups = image_ai.find_duplicates(img, [(n, pa) for n, pa in paths if os.path.exists(pa)])
    dup_payload = []
    for name, sim, same in dups:
        owner = Product.query.filter_by(image=name).first()
        dup_payload.append({
            "image": name,
            "sim": sim,
            "same": same,
            "product_id": owner.id if owner else None,
            "title": owner.title if owner else "",
        })

    result = {
        "ok": True,
        "size": list(img.size),
        "ai": {"score": score, "verdict": image_ai.verdict_of(score), "reasons": reasons},
        "duplicates": dup_payload,
        "is_duplicate": bool(dup_payload and dup_payload[0]["same"]),
    }

    ref = request.files.get("reference")
    if ref:
        try:
            ref_img = image_ai.load_image(ref.stream)
            result["compare"] = image_ai.compare(img, ref_img)
        except Exception:
            result["compare"] = None

    return jsonify(result)


@bp.route("/scan", methods=["POST"])
def scan_item():
    """扫物识别：上传一张图，匹配站内最相似的商品，给出品类/型号/估价。"""
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "message": "没有收到图片"}), 400
    try:
        img = image_ai.load_image(f.stream)
    except Exception:
        return jsonify({"ok": False, "message": "图片无法解析"}), 400

    target = image_ai.dhash(img)
    best, best_sim = None, 0.0
    for p in Product.query.filter(Product.status == "onsale").limit(400).all():
        if not p.image:
            continue
        h = image_ai.hash_of_file(os.path.join(Config.UPLOAD_FOLDER, p.image))
        if h is None:
            continue
        sim = image_ai.similarity(target, h)
        if sim > best_sim:
            best, best_sim = p, sim

    score, reasons = image_ai.ai_traces(img, image_ai.read_meta(img))
    label = "未匹配到同款" if not best else ("高度相似" if best_sim >= 0.88 else "相似商品")

    out = {
        "ok": True,
        "recognized": bool(best) and best_sim >= 0.7,
        "label": label,
        "similarity": round(best_sim, 3),
        "ai_trace": {"score": score, "verdict": image_ai.verdict_of(score), "reasons": reasons},
    }
    if best:
        cls = ai_engine.classify_product(best.title, best.description or "")
        out["match"] = {
            "id": best.id,
            "title": best.title,
            "category": cls["category"],
            "condition": best.condition,
            "price": best.price,
            "image": "/static/uploads/" + best.image,
        }
        prices = sorted([x.price for x in Product.query.filter_by(category_id=best.category_id, status="onsale") if x.price])
        if prices:
            out["price_range"] = [prices[0], prices[-1], prices[len(prices) // 2]]
    return jsonify(out)


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
