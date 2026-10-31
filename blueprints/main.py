from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

import ai_engine
import llm
import search_engine
from config import Config
from models import Behavior, Category, Product, SearchHistory, db

bp = Blueprint("main", __name__)


def _behaviors():
    if not current_user.is_authenticated:
        return []
    return (Behavior.query.filter_by(user_id=current_user.id)
            .order_by(Behavior.id.desc()).limit(60).all())


@bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    cat_id = request.args.get("cat", type=int)
    keyword = (request.args.get("q") or "").strip()
    per_page = Config.PER_PAGE

    if keyword and current_user.is_authenticated:
        _remember_search(keyword)

    on_sale = Product.query.filter_by(status="onsale")
    if cat_id:
        on_sale = on_sale.filter_by(category_id=cat_id)
    pool = on_sale.all()

    mode, intent, hit_terms = "本地推荐", "", []
    rows, pages, likes = [], None, []

    if keyword:
        behaviors = _behaviors()

        # 1) 本地语义检索：TF-IDF + 同义词 + 个性化加权
        rows, hit_terms = search_engine.rank(pool, keyword, current_user, behaviors, limit=48)
        mode = "本地语义检索"

        # 2) 配了大模型就先做查询理解，再做重排（失败自动忽略）
        expanded = llm.expand_query(keyword) if llm.enabled() else None
        if expanded:
            intent = expanded.get("intent", "")
            kws = expanded.get("keywords") or []
            if kws:
                rows2, _ = search_engine.rank(pool, " ".join(kws), current_user, behaviors, limit=48)
                seen = {r["product"].id for r in rows2}
                rows = rows2 + [r for r in rows if r["product"].id not in seen]
            mode = "AI 增强检索"

        reranked = llm.rerank(keyword, rows) if rows else None
        if reranked:
            rows = reranked

        # 3) 搜索页底部“猜你喜欢”
        likes, _ = search_engine.rank(pool, "", current_user, behaviors, limit=8, fill=True)
        shown = {r["product"].id for r in rows}
        likes = [r for r in likes if r["product"].id not in shown][:4]

        start = (page - 1) * per_page
        pages = {
            "page": page,
            "pages": max(1, (len(rows) + per_page - 1) // per_page),
            "has_prev": page > 1,
            "has_next": page * per_page < len(rows),
            "prev_num": page - 1,
            "next_num": page + 1,
        }
        rows = rows[start:start + per_page]
        title = f"搜索「{keyword}」"
    elif cat_id:
        cat = Category.query.get(cat_id)
        rows = [{"product": p, "reason": "", "score": 0, "matched": []} for p in pool]
        rows.sort(key=lambda r: r["product"].created_at, reverse=True)
        start = (page - 1) * per_page
        pages = {
            "page": page,
            "pages": max(1, (len(rows) + per_page - 1) // per_page),
            "has_prev": page > 1,
            "has_next": page * per_page < len(rows),
            "prev_num": page - 1,
            "next_num": page + 1,
        }
        rows = rows[start:start + per_page]
        title = f"分类 · {cat.name if cat else ''}"
    else:
        behaviors = _behaviors()
        if current_user.is_authenticated:
            rows, _ = search_engine.rank(pool, "", current_user, behaviors, limit=per_page, fill=True)
            title = "为你推荐"
            mode = "个性化推荐"
        else:
            items = ai_engine.recommend_products(current_user, limit=per_page)
            rows = [{"product": p, "reason": "热门", "score": 0, "matched": []} for p in items]
            title = "热门商品"
            mode = "热门榜"

    hot = (Product.query.filter_by(status="onsale").order_by(Product.views.desc()).limit(5).all()
           if not keyword else [])

    return render_template(
        "index.html", rows=rows, likes=likes, pages=pages, title=title,
        active_cat=cat_id, keyword=keyword, hot=hot,
        mode=mode, intent=intent, hit_terms=hit_terms,
        llm_status=llm.status(),
        on_sale_count=Product.query.filter_by(status="onsale").count(),
        recent_searches=_recent_searches(),
    )


def _remember_search(keyword):
    """同一关键词只留一条：重复搜索累加次数并置顶。"""
    row = SearchHistory.query.filter_by(user_id=current_user.id, keyword=keyword).first()
    if row:
        row.times = (row.times or 1) + 1
        row.updated_at = db.func.now()
    else:
        db.session.add(SearchHistory(user_id=current_user.id, keyword=keyword))
    db.session.commit()
    # 只保留最近 20 条
    extra = (SearchHistory.query.filter_by(user_id=current_user.id)
             .order_by(SearchHistory.updated_at.desc()).offset(20).all())
    for e in extra:
        db.session.delete(e)
    db.session.commit()


def _recent_searches(limit=8):
    if not current_user.is_authenticated:
        return []
    return (SearchHistory.query.filter_by(user_id=current_user.id)
            .order_by(SearchHistory.updated_at.desc()).limit(limit).all())


@bp.route("/search-history/clear", methods=["POST"])
def clear_search_history():
    from flask import redirect, url_for
    if current_user.is_authenticated:
        SearchHistory.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "campus-secondhand", "version": "1.1.0",
                    "llm": llm.status()})


@bp.route("/api/search")
def api_search():
    """前端联想用：返回排好序的商品 + 推荐理由。"""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"items": []})
    pool = Product.query.filter_by(status="onsale").all()
    rows, _ = search_engine.rank(pool, q, current_user, _behaviors(), limit=8)
    return jsonify({"items": [{
        "id": r["product"].id, "title": r["product"].title,
        "price": r["product"].price, "reason": r["reason"],
    } for r in rows]})
