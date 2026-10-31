"""蓝图集中注册：app.py 只调一个函数。"""


def register_blueprints(app):
    from blueprints import admin, ai, auth, cart, history, main, message, order, product

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp, url_prefix="/auth")
    app.register_blueprint(product.bp, url_prefix="/product")
    app.register_blueprint(order.bp, url_prefix="/order")
    app.register_blueprint(message.bp, url_prefix="/message")
    app.register_blueprint(ai.bp, url_prefix="/ai")
    app.register_blueprint(admin.bp, url_prefix="/admin")
    app.register_blueprint(cart.bp, url_prefix="/cart")
    app.register_blueprint(history.bp, url_prefix="/history")
