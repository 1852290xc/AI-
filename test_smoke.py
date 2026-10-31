"""冒烟测试：用 test client 模拟浏览器，覆盖 24 个关键点。

    python test_smoke.py
"""
import os
import sys

from app import create_app
from config import Config
from models import CartItem, Category, Order, Product, User, db
from init_db import seed_data

TEST_DB = os.path.join(Config.__dict__.get("BASE_DIR", os.path.dirname(__file__)), "data", "test_smoke.db")

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    mark = "✅" if cond else "❌"
    print(f"{mark} {name}" + (f"　— {detail}" if detail and not cond else ""))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(os.path.dirname(__file__), "data", "test_smoke.db")
    WTF_CSRF_ENABLED = False


def main():
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_data()

        client = app.test_client()

        # ---------------- 游客 ----------------
        r = client.get("/")
        check("1. 游客能访问首页", r.status_code == 200 and "智汇校园" in r.get_data(as_text=True))

        cat = Category.query.first()
        r = client.get(f"/?cat={cat.id}")
        check("2. 分类筛选可用", r.status_code == 200 and cat.name in r.get_data(as_text=True))

        r = client.get("/?q=iPhone")
        check("3. 关键词搜索可用", r.status_code == 200 and "iPhone" in r.get_data(as_text=True))
        r = client.get("/about")
        check("4. 关于页可访问", r.status_code == 200)

        # ---------------- 注册 / 登录 ----------------
        r = client.post("/auth/register", data={
            "student_id": "2099001", "nickname": "测试同学", "school": "示范大学",
            "email": "test1@campus.edu", "password": "abc123", "confirm": "abc123",
        }, follow_redirects=True)
        check("5. 注册成功并自动登录", r.status_code == 200 and User.query.filter_by(student_id="2099001").first() is not None)

        client.get("/auth/logout")
        r = client.post("/auth/register", data={
            "student_id": "2099001", "nickname": "重复", "school": "示范大学",
            "email": "test1@campus.edu", "password": "abc123", "confirm": "abc123",
        }, follow_redirects=True)
        check("6. 重复注册被拒绝", "已经注册" in r.get_data(as_text=True))

        client.get("/auth/logout")
        r = client.post("/auth/login", data={"account": "2099001", "password": "abc123"}, follow_redirects=True)
        check("7. 登录成功", r.status_code == 200 and "测试同学" in r.get_data(as_text=True))

        client.get("/auth/logout")
        r = client.post("/auth/login", data={"account": "2099001", "password": "wrong"}, follow_redirects=True)
        check("8. 错误密码被拒绝", "不正确" in r.get_data(as_text=True))

        # ---------------- AI 接口 ----------------
        r = client.post("/ai/classify", json={"title": "九成新 iPhone 13", "description": ""})
        check("9. AI 分类接口判断为数码电子", r.json["category"] == "数码电子", str(r.json))

        r = client.post("/ai/price", json={"original_price": 5999, "condition": "九成新"})
        check("10. AI 定价返回合理区间", r.json["low"] < r.json["suggest"] < r.json["high"])

        r = client.post("/ai/chat", json={"question": "怎么发布商品？"})
        check("11. AI 客服能回答常见问题", r.json["matched"] and len(r.json["answer"]) > 5)

        r = client.post("/ai/moderate", json={"text": "低价出外挂，需要的私聊"})
        check("12. AI 审核能拦截违规内容", r.json["passed"] is False)

        # ---------------- 发布商品 ----------------
        client.post("/auth/login", data={"account": "zhangsan", "password": "123456"})
        before = Product.query.count()
        r = client.post("/product/publish", data={
            "title": "九成新 iPad mini 6 64G", "description": "自用半年，无划痕",
            "price": "1999", "original_price": "3799", "condition": "九成新", "category_id": "",
        }, follow_redirects=True)
        new = Product.query.filter_by(title="九成新 iPad mini 6 64G").first()
        check("13. 发布商品成功且 AI 自动分类", r.status_code == 200 and new is not None and new.category.name == "数码电子")

        r = client.post("/product/publish", data={
            "title": "代写论文服务", "description": "包过，价格好商量",
            "price": "500", "original_price": "1000", "condition": "全新", "category_id": "",
        }, follow_redirects=True)
        check("14. 违规商品被拦截", Product.query.count() == before + 1 and "拦截" in r.get_data(as_text=True))

        # ---------------- 收藏 ----------------
        pid = new.id
        r = client.post(f"/product/{pid}/favorite")
        check("15. 收藏成功", r.json["ok"] and r.json["favorited"] is True)
        r = client.post(f"/product/{pid}/favorite")
        check("16. 取消收藏成功", r.json["ok"] and r.json["favorited"] is False)

        # ---------------- 下单 ----------------
        other = Product.query.filter(Product.seller_id != User.query.filter_by(student_id="zhangsan").first().id).first()
        r = client.post(f"/order/create/{other.id}", follow_redirects=True)
        order = Order.query.filter_by(product_id=other.id).first()
        check("17. 下单成功且商品转为已售",
              r.status_code == 200 and order is not None and db.session.get(Product, other.id).status == "sold")

        mine = Product.query.filter_by(seller_id=User.query.filter_by(student_id="zhangsan").first().id).first()
        r = client.post(f"/order/create/{mine.id}", follow_redirects=True)
        check("18. 不能购买自己的商品", "不能购买自己" in r.get_data(as_text=True))

        r = client.post(f"/order/create/{other.id}", follow_redirects=True)
        check("19. 重复下单被拦截", "已经下过单" in r.get_data(as_text=True) or "不能购买" in r.get_data(as_text=True))

        # ---------------- 私信 ----------------
        lisi = User.query.filter_by(student_id="lisi").first()
        r = client.post("/message/send", json={"to": lisi.id, "content": "同学，这个还在吗？"})
        check("20. 私信发送成功", r.json["ok"] is True)

        r = client.post("/message/send", json={"to": lisi.id, "content": "你这傻逼东西"})
        check("21. 私信违规内容被拦截", r.json["ok"] is False and r.json.get("blocked"))

        # ---------------- 后台权限 ----------------
        r = client.get("/admin/", follow_redirects=False)
        check("22. 普通用户访问后台被拒绝", r.status_code == 403)

        client.get("/auth/logout")
        client.post("/auth/login", data={"account": "admin", "password": "admin123"})
        r = client.get("/admin/")
        check("23. 管理员可进后台", r.status_code == 200 and "管理看板" in r.get_data(as_text=True))

        r = client.get("/auth/logout", follow_redirects=True)
        check("24. 退出登录正常", "已退出登录" in r.get_data(as_text=True))

        # ---------------- 检索与个性化推荐 ----------------
        r = client.get("/?q=%E9%94%AE%E7%9B%98")
        body = r.get_data(as_text=True)
        check("25. 搜索「键盘」能命中机械键盘", r.status_code == 200 and "机械键盘" in body)

        r = client.get("/?q=%E4%BE%BF%E5%AE%9C%E7%9A%84%E5%B9%B3%E6%9D%BF")
        check("26. 口语查询「便宜的平板」能命中 iPad",
              "iPad" in r.get_data(as_text=True))

        client.post("/auth/login", data={"account": "zhangsan", "password": "123456"})
        r = client.get("/?q=%E7%81%AF")
        b = r.get_data(as_text=True)
        check("27. 登录后搜索页出现个性化推荐与理由",
              "猜你喜欢" in b and ("✦" in b))

        r = client.get("/api/health")
        check("28. 健康检查返回大模型接入状态", r.status_code == 200 and "llm" in (r.json or {}))

        # ---------------- 购物车 / 浏览记录 / 搜索记录 ----------------
        client.get("/auth/logout")
        client.post("/auth/login", data={"account": "lisi", "password": "123456"})
        target = Product.query.filter(Product.seller_id != User.query.filter_by(student_id="lisi").first().id,
                                      Product.status == "onsale").first()
        r = client.post(f"/cart/add/{target.id}")
        check("29. 加入购物车成功", r.json and r.json.get("ok") is True and r.json.get("count", 0) >= 1)

        r = client.get("/cart/")
        check("30. 购物车页面显示该商品", r.status_code == 200 and target.title in r.get_data(as_text=True))

        cart_item = CartItem.query.filter_by(product_id=target.id).first()
        before_orders = Order.query.count()
        r = client.post("/cart/checkout", data={"ids": str(cart_item.id)}, follow_redirects=True)
        check("31. 结算选中商品并生成订单", Order.query.count() == before_orders + 1)

        client.get(f"/product/{target.id}")
        r = client.get("/history/")
        check("32. 浏览记录按时间倒序列出", r.status_code == 200 and target.title in r.get_data(as_text=True))

        client.get("/?q=%E9%94%AE%E7%9B%98")
        r = client.get("/?q=%E9%94%AE%E7%9B%98")
        check("33. 搜索记录被记住并展示", "最近搜索" in r.get_data(as_text=True))

        # ---------------- 发布助手（类型/型号/成色/估价） ----------------
        client.get("/auth/logout")
        client.post("/auth/login", data={"account": "zhangsan", "password": "123456"})
        r = client.post("/ai/analyze", json={
            "title": "九成新 iPhone 13 128G 星光色",
            "description": "自用一年，电池健康 87%",
            "original_price": 5999,
        })
        j = r.json or {}
        check("34. 发布助手识别型号与成色",
              j.get("ok") is True and "iPhone 13" in " ".join(j.get("model", [])) and j.get("condition") == "九成新")

        check("35. 发布助手给出估价区间与建议",
              j.get("value", {}).get("low", 0) < j.get("value", {}).get("mid", 0) <= j.get("value", {}).get("high", 0)
              and len(j.get("advice", [])) >= 2)

        r = client.get("/product/publish")
        check("36. 发布页包含 AI 助手面板", r.status_code == 200 and "AI 发布助手" in r.get_data(as_text=True))

        # ---------------- 定位与附近优先 ----------------
        client.get("/auth/logout")
        r = client.post("/api/location", json={"lat": 39.9990, "lng": 116.3260})
        check("37. 提交定位返回最近校区",
              r.status_code == 200 and r.json.get("ok") and r.json.get("campus") == "清华大学")

        r = client.get("/")
        body = r.get_data(as_text=True)
        check("38. 首页按附近校区优先展示", "已按「清华大学」附近" in body)

        r = client.post("/api/location", json={"lat": 999, "lng": 999})
        check("39. 非法坐标被拒绝", r.status_code == 400 and r.json.get("ok") is False)

        # ---------------- 全国高校地图 ----------------
        client.post("/api/location", json={"lat": 39.9990, "lng": 116.3260})
        r = client.get("/map")
        body = r.get_data(as_text=True)
        check("40. 地图页渲染全国高校", r.status_code == 200 and "全国高校地图" in body and "清华大学" in body)

        import re as _re
        def _count(html):
            m = _re.search(r"当前半径内：(\d+) 件商品", html)
            return int(m.group(1)) if m else -1

        far = Product.query.filter_by(status="onsale").first()
        far.campus = "新疆大学"
        db.session.commit()
        small = _count(client.get("/map?r=5").get_data(as_text=True))
        large = _count(client.get("/map?r=0").get_data(as_text=True))
        check("41. 半径筛选改变商品数量", 0 < small < large)

        r = client.get("/map?r=999")
        check("42. 非法半径回退不报错", r.status_code == 200)

        # ---------------- 图片查重 / AI 痕迹 ----------------
        import io as _io
        from models import Product as _P
        from PIL import Image as _Img
        _buf = _io.BytesIO()
        _Img.new("RGB", (600, 600), (120, 140, 200)).save(_buf, "JPEG")
        raw = _buf.getvalue()
        sample = _P.query.first()
        sample.image = "t_check.jpg"
        _upload = os.path.join("static", "uploads", "t_check.jpg")
        os.makedirs(os.path.dirname(_upload), exist_ok=True)
        with open(_upload, "wb") as fh:
            fh.write(raw)
        db.session.commit()

        r = client.post("/ai/image-check", data={"file": (_io.BytesIO(raw), "a.jpg")},
                        content_type="multipart/form-data")
        j = r.json or {}
        check("43. 图片检测返回 AI 痕迹评分", r.status_code == 200 and "ai" in j and "score" in j["ai"])

        top = (j.get("duplicates") or [{}])[0]
        check("44. 同图能被查重命中", j.get("is_duplicate") is True and top.get("same") is True)

        r = client.post("/ai/image-check",
                        data={"file": (_io.BytesIO(raw), "a.jpg"), "reference": (_io.BytesIO(raw), "b.jpg")},
                        content_type="multipart/form-data")
        cmp = (r.json or {}).get("compare") or {}
        check("45. 与参考图比对判定为同一张", cmp.get("same") is True and cmp.get("phash_sim", 0) > 0.9)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print()
    if passed == total:
        print(f"✅ 全部通过！{passed}/{total}")
        return 0
    print(f"❌ 通过 {passed}/{total}，失败项：")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"   - {name} {detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
