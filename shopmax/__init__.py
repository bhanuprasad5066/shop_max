import logging
import os
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from .auth import auth_bp
from .cart import cart_bp
from .checkout import checkout_bp
from .config import Config
from .db import close_db
from .extensions import init_extensions
from .store import store_bp


def _configure_logging(app):
    if app.logger.handlers:
        return

    log_level = logging.INFO
    app.logger.setLevel(log_level)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    log_path = os.path.join(project_root, "shopmax.log")
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=2)
    handler.setLevel(log_level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app.logger.addHandler(handler)


def _wants_json_response():
    best = request.accept_mimetypes.best
    if request.path.startswith("/auth/api"):
        return True
    if best == "application/json":
        return request.accept_mimetypes[best] >= request.accept_mimetypes["text/html"]
    return False


def _register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        app.logger.warning("HTTP error %s at %s", error.code, request.path)
        if _wants_json_response():
            return jsonify(
                {
                    "error": error.name,
                    "message": error.description,
                    "status": error.code,
                }
            ), error.code

        return (
            render_template(
                "error.html",
                code=error.code,
                title=error.name,
                message=error.description,
            ),
            error.code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        app.logger.exception("Unhandled exception at %s", request.path)
        if _wants_json_response():
            return (
                jsonify(
                    {
                        "error": "Internal Server Error",
                        "message": "Something went wrong. Please try again.",
                        "status": 500,
                    }
                ),
                500,
            )

        return (
            render_template(
                "error.html",
                code=500,
                title="Internal Server Error",
                message="Something went wrong. Please try again.",
            ),
            500,
        )


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

    init_extensions(app)
    _configure_logging(app)
    _register_error_handlers(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(checkout_bp)

    app.teardown_appcontext(close_db)
    return app
