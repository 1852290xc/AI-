import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """全局配置：密钥、数据库、上传限制、站点信息。"""

    SECRET_KEY = os.environ.get("SECRET_KEY", "zhihui-campus-2026-please-change-me")

    # SQLite 放在 data/ 下，免安装数据库
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "data", "campus_market.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024          # 单张图片最大 5MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

    # 站点
    SITE_NAME = "智汇校园 · 二手集市"
    SITE_SLOGAN = "AI 驱动的可信校园闲置交易平台"
    PER_PAGE = 12
