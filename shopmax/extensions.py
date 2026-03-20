from celery import Celery
from flask_caching import Cache
from flask_jwt_extended import JWTManager

cache = Cache()
jwt = JWTManager()
celery = Celery(__name__)


def init_extensions(app):
    jwt.init_app(app)

    cache_config = {
        "CACHE_TYPE": app.config.get("CACHE_TYPE", "SimpleCache"),
        "CACHE_DEFAULT_TIMEOUT": app.config.get("CACHE_DEFAULT_TIMEOUT", 120),
    }
    if cache_config["CACHE_TYPE"] == "RedisCache":
        cache_config["CACHE_REDIS_URL"] = app.config.get("CACHE_REDIS_URL")
    cache.init_app(app, config=cache_config)

    celery.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL"),
        result_backend=app.config.get("CELERY_RESULT_BACKEND"),
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        enable_utc=False,
        timezone="Asia/Kolkata",
    )

    class FlaskTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask

    # Ensure task modules are loaded after Celery is configured.
    from . import tasks  # noqa: F401


@jwt.unauthorized_loader
def _jwt_unauthorized(message):
    return {"error": "unauthorized", "message": message}, 401


@jwt.invalid_token_loader
def _jwt_invalid_token(message):
    return {"error": "invalid_token", "message": message}, 422


@jwt.expired_token_loader
def _jwt_expired(_jwt_header, _jwt_payload):
    return {"error": "token_expired", "message": "Token expired"}, 401
