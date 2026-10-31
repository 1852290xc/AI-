from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

import ai_engine
from models import Message, User, db

bp = Blueprint("message", __name__)


@bp.route("/inbox")
@login_required
def inbox():
    rows = (Message.query
            .filter(or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id))
            .order_by(Message.created_at.desc()).all())

    conversations = {}
    for m in rows:
        other_id = m.receiver_id if m.sender_id == current_user.id else m.sender_id
        conv = conversations.setdefault(other_id, {"user": db.session.get(User, other_id),
                                                   "last": m, "unread": 0})
        if m.receiver_id == current_user.id and not m.is_read:
            conv["unread"] += 1

    ordered = sorted(conversations.values(), key=lambda c: c["last"].created_at, reverse=True)
    return render_template("message/inbox.html", conversations=ordered)


@bp.route("/chat/<int:uid>")
@login_required
def chat(uid):
    other = User.query.get_or_404(uid)
    msgs = (Message.query
            .filter(or_(
                db.and_(Message.sender_id == current_user.id, Message.receiver_id == uid),
                db.and_(Message.sender_id == uid, Message.receiver_id == current_user.id)))
            .order_by(Message.created_at.asc()).all())

    for m in msgs:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    db.session.commit()

    return render_template("message/chat.html", other=other, messages=msgs)


@bp.route("/send", methods=["POST"])
@login_required
def send():
    data = request.get_json(silent=True) or request.form
    to_id = data.get("to") or data.get("to_id")
    content = (data.get("content") or "").strip()

    if not content:
        return jsonify({"ok": False, "message": "消息不能为空"}), 400
    if len(content) > 500:
        return jsonify({"ok": False, "message": "消息太长了"}), 400

    verdict = ai_engine.moderate_text(content)
    if not verdict["passed"]:
        return jsonify({"ok": False, "blocked": True, "message": verdict["message"]}), 200

    try:
        to_id = int(to_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "收件人不存在"}), 400

    other = User.query.get(to_id)
    if not other:
        return jsonify({"ok": False, "message": "收件人不存在"}), 404

    msg = Message(sender_id=current_user.id, receiver_id=to_id, content=content)
    db.session.add(msg)
    db.session.commit()

    return jsonify({
        "ok": True,
        "message": {"id": msg.id, "content": msg.content,
                    "mine": True, "time": msg.created_at.strftime("%H:%M")},
    })


@bp.route("/poll/<int:uid>")
@login_required
def poll(uid):
    """前端每 5 秒拉一次新消息。"""
    since = request.args.get("since", 0, type=int)
    msgs = (Message.query
            .filter(Message.id > since)
            .filter(or_(
                db.and_(Message.sender_id == current_user.id, Message.receiver_id == uid),
                db.and_(Message.sender_id == uid, Message.receiver_id == current_user.id)))
            .order_by(Message.created_at.asc()).all())

    return jsonify([{
        "id": m.id, "content": m.content, "mine": m.sender_id == current_user.id,
        "time": m.created_at.strftime("%H:%M"),
    } for m in msgs])
