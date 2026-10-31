from flask import Blueprint, jsonify, render_template, request, session
from flask_login import current_user

import ai_engine
import campus
import llm
from china_geo import CHINA_PATH
import search_engine
import taxonomy
from config import Config
from models import Behavior, Category, Product, SearchHistory, db

bp = Blueprint("main", __name__)


def _location():
    """优先用会话里的定位，其次用账号里保存的。"""
    lat = session.get("lat")
    lng = session.get("lng")
    if lat is None and current_user.is_authenticated:
        lat, lng = current_user.lat, current_user.lng
    if lat is None or lng is None:
        return None, None
    return float(lat), float(lng)


@bp.route("/api/location", methods=["POST"])
def set_location():
    d = request.get_json(silent=True) or request.form
    try:
        lat = float(d.get("lat"))
        lng = float(d.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "坐标无效"}), 400
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"ok": False, "message": "坐标超出范围"}), 400

    session["lat"], session["lng"] = lat, lng
    if current_user.is_authenticated:
        current_user.lat, current_user.lng = lat, lng
        db.session.commit()

    name, km = campus.nearest_campus(lat, lng)
    return jsonify({"ok": True, "campus": name, "km": round(km, 1) if km else None})


@bp.route("/api/location", methods=["DELETE"])
def clear_location():
    session.pop("lat", None)
    session.pop("lng", None)
    if current_user.is_authenticated:
        current_user.lat = current_user.lng = None
        db.session.commit()
    return jsonify({"ok": True})


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
    group_key = (request.args.get("g") or "").strip()
    sub_name = (request.args.get("sub") or "").strip()
    # 子类筛选走 taxo_sub，大类筛选走子类集合
    per_page = Config.PER_PAGE

    if keyword and current_user.is_authenticated:
        _remember_search(keyword)

    on_sale = Product.query.filter_by(status="onsale")
    if cat_id:
        on_sale = on_sale.filter_by(category_id=cat_id)
    pool = on_sale.all()
    if sub_name:
        pool = [x for x in pool if (x.taxo_sub or "") == sub_name]
    elif group_key:
        _subs = [x[0] for x in (taxonomy.BY_KEY.get(group_key) or {}).get("subs", [])]
        if _subs:
            pool = [x for x in pool if (x.taxo_sub or "") in _subs]

    lat, lng = _location()
    mode, intent, hit_terms = "本地推荐", "", []
    rows, pages, likes = [], None, []

    if keyword:
        behaviors = _behaviors()

        # 1) 本地语义检索：TF-IDF + 同义词 + 个性化加权
        rows, hit_terms = search_engine.rank(pool, keyword, current_user, behaviors, limit=48, lat=lat, lng=lng)
        mode = "本地语义检索"

        # 2) 配了大模型就先做查询理解，再做重排（失败自动忽略）
        expanded = llm.expand_query(keyword) if llm.enabled() else None
        if expanded:
            intent = expanded.get("intent", "")
            kws = expanded.get("keywords") or []
            if kws:
                rows2, _ = search_engine.rank(pool, " ".join(kws), current_user, behaviors, limit=48, lat=lat, lng=lng)
                seen = {r["product"].id for r in rows2}
                rows = rows2 + [r for r in rows if r["product"].id not in seen]
            mode = "AI 增强检索"

        reranked = llm.rerank(keyword, rows) if rows else None
        if reranked:
            rows = reranked

        # 3) 搜索页底部“猜你喜欢”
        likes, _ = search_engine.rank(pool, "", current_user, behaviors, limit=8, fill=True, lat=lat, lng=lng)
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
    elif not keyword and (group_key or sub_name):
        rows, _ = search_engine.rank(pool, "", current_user if current_user.is_authenticated else None,
                                     _behaviors(), limit=per_page, lat=lat, lng=lng, fill=False)
        rows = [dict(r, reason=r.get("reason") or "分类命中") for r in rows]
        title = (sub_name or (taxonomy.BY_KEY.get(group_key) or {}).get("name") or "分类") + " · 在售"
        mode = "分类浏览"
    else:
        behaviors = _behaviors()
        if current_user.is_authenticated:
            rows, _ = search_engine.rank(pool, "", current_user, behaviors, limit=per_page, fill=True, lat=lat, lng=lng)
            title = "为你推荐"
            mode = "个性化推荐"
        elif lat is not None and lng is not None:
            rows, _ = search_engine.rank(pool, "", None, [], limit=per_page, lat=lat, lng=lng)
            title = "附近商品"
            mode = "按距离优先"
            for r in rows:
                if r.get("distance") is not None:
                    r["reason"] = "离你最近"
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
        located=lat is not None,
        groups=taxonomy.GROUPS, group_key=group_key, sub_name=sub_name,
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


@bp.route("/map")
def map_view():
    """全国高校地图：标注距离，支持 5/10/50/100 km 半径筛选。"""
    lat, lng = _location()
    radius = request.args.get("r", 50, type=int)
    if radius not in (5, 10, 50, 100, 0):
        radius = 50

    unis = campus.all_campuses(lat, lng)
    for u in unis:
        u["in"] = radius == 0 or (u["km"] is not None and u["km"] <= radius)
        u["x"] = round((u["lng"] - 73.0) / (135.5 - 73.0) * 900, 1)
        u["y"] = round((53.8 - u["lat"]) / (53.8 - 18.0) * 600, 1)

    # 商品按卖家校区是否在半径内筛选
    pool = Product.query.filter_by(status="onsale").all()
    shown, cutoff = [], {}
    for p in pool:
        school = p.campus or (p.seller.school if p.seller else "")
        c = campus.coords(school)
        d = campus.distance_km(lat, lng, c[0], c[1]) if (c and lat is not None) else None
        if radius == 0 or d is None or (d is not None and d <= radius):
            shown.append({"product": p, "distance": round(d, 1) if d is not None else None,
                          "reason": f"来自{school}" if school else "校园闲置"})

    shown.sort(key=lambda r: (r["distance"] is None, r["distance"] or 0))
    nearest = [u for u in unis if u["km"] is not None][:8]
    label_unis = []
    ux = round((lng - 73.0) / (135.5 - 73.0) * 900, 1) if lng else 0
    uy = round((53.8 - lat) / (53.8 - 18.0) * 600, 1) if lat else 0
    for i, u in enumerate(nearest[:5]):
        v = dict(u)
        # 标签统一排在定位点右侧并纵向错开，避免北京高校扎堆重叠
        v["lx"] = ux + 20
        v["ly"] = uy - 30 + i * 17
        label_unis.append(v)

    return render_template(
        "map.html", unis=unis, nearest=nearest, radius=radius,
        rows=shown[:12], total=len(shown), located=lat is not None,
        user_lat=lat, user_lng=lng,
        user_x=round((lng - 73.0) / (135.5 - 73.0) * 900, 1) if lng else None,
        user_y=round((53.8 - lat) / (53.8 - 18.0) * 600, 1) if lat else None,
        china_path=CHINA_PATH, label_unis=label_unis,
        loc_campus=(campus.nearest_campus(lat, lng)[0] if lat is not None else ""),
    )


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/api/products")
def api_products():
    """给单文件前端用的商品列表（JSON）。"""
    from flask import request

    q = (request.args.get("q") or "").strip()
    cat = request.args.get("cat") or ""
    rows = Product.query.filter_by(status="onsale").order_by(Product.created_at.desc()).all()
    items = []
    for p in rows:
        cname = p.category.name if p.category else "其他"
        if cat and cat != "全部" and cname != cat:
            continue
        if q and q.lower() not in (p.title or "").lower() and q not in cname:
            continue
        items.append({
            "id": p.id,
            "t": p.title,
            "p": int(p.price or 0),
            "o": int(p.original_price or 0),
            "c": p.condition or "",
            "cat": cname,
            "s": p.seller.school if p.seller else "",
            "v": p.views or 0,
            "img": ("/static/uploads/" + p.image) if p.image else "",
            "cmp": p.campus or (p.seller.school if p.seller else ""),
            "sub": p.taxo_sub or "",
        })
    return jsonify({"ok": True, "count": len(items), "items": items})


@bp.route("/web")
def web_app():
    """单文件交互版页面（由 tools/make_spa.py 生成到 static/app.html）。"""
    import os

    from flask import current_app, send_from_directory

    path = os.path.join(current_app.static_folder, "app.html")
    if not os.path.exists(path):
        return ("静态前端未生成，请先运行 tools/make_spa.py", 404)
    return send_from_directory(current_app.static_folder, "app.html")


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
