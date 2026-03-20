from datetime import datetime

from .extensions import celery


@celery.task(name="shopmax.tasks.process_post_order")
def process_post_order(order_id, user_id, user_email):
    # This task is intentionally lightweight and safe to retry.
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "status": "queued_and_processed",
        "order_id": order_id,
        "user_id": user_id,
        "user_email": user_email,
        "processed_at": now,
    }
