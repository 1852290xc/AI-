import os

from flask import Flask, render_template
from flask_login import LoginManager

from config import Config
from models import Category, User, db

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 目录兜底：data/ 与 uploads/ 必须存在
    os.makedirs(os.path.join(app.root_path, "data"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录后再进行这个操作。"
    login_manager.login_message_category = "warning"

    from blueprints import register_blueprints

    register_blueprints(app)

    @app.context_processor
    def inject_globals():
        try:
            cats = Category.query.order_by(Category.sort).all()
        except Exception:  # 数据库还没初始化时也不该把页面拖垮
            cats = []
        return {
            "site_name": app.config["SITE_NAME"],
            "slogan": app.config["SITE_SLOGAN"],
            "categories": cats,
            "site_year": 2026,
        }

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="这个页面走丢了"), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template("error.html", code=413, message="图片太大了，请压缩到 5MB 以内"), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
