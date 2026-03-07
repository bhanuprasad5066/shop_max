import os
from flask import Flask
from dotenv import load_dotenv

from .config import Config
from .db import close_db
from .auth import auth_bp
from .store import store_bp
from .cart import cart_bp
from .checkout import checkout_bp


def create_app():
    load_dotenv()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, "templates"),
        static_folder=os.path.join(project_root, "static"),
    )
    app.config.from_object(Config)

    secret_key = os.getenv("SECRET_KEY", app.config["SECRET_KEY"])
    app.config["SECRET_KEY"] = secret_key

    app.register_blueprint(auth_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(checkout_bp)

    app.teardown_appcontext(close_db)
    return app