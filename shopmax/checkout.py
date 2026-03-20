from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .db import get_db, query_all, query_one
from .extensions import cache
from .tasks import process_post_order
from .utils import login_required

try:
    import razorpay
except ImportError:  # pragma: no cover
    razorpay = None


checkout_bp = Blueprint("checkout", __name__)
CANCELLABLE_STATUSES = {"PAID", "COD_PENDING", "PLACED"}


def _to_decimal(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _invalidate_catalog_cache():
    try:
        cache.clear()
    except Exception:
        current_app.logger.warning("Cache invalidation failed", exc_info=True)


def _enqueue_post_order_task(order_id):
    user = query_one("SELECT email FROM users WHERE id = %s", (session["user_id"],))
    user_email = user["email"] if user else ""

    try:
        process_post_order.delay(order_id, session["user_id"], user_email)
    except Exception:
        current_app.logger.warning(
            "Unable to enqueue post-order task for order_id=%s",
            order_id,
            exc_info=True,
        )


def _get_checkout_cart():
    cart = session.get("cart", {})
    items = []
    subtotal = Decimal("0.00")

    for product_id, qty in cart.items():
        quantity = int(qty)
        if quantity <= 0:
            continue

        product = query_one(
            "SELECT id, name, brand, price, image_url, stock FROM products WHERE id = %s AND is_active = 1",
            (int(product_id),),
        )
        if not product:
            continue

        unit_price = _to_decimal(product["price"])
        line_total = (unit_price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal += line_total

        items.append(
            {
                "id": product["id"],
                "name": product["name"],
                "brand": product["brand"],
                "image_url": product["image_url"],
                "stock": int(product["stock"]),
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    return items, subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_razorpay_client():
    if razorpay is None:
        return None, "Razorpay SDK is missing. Install dependencies from requirements.txt."

    key = current_app.config.get("RAZORPAY_KEY", "").strip()
    secret = current_app.config.get("RAZORPAY_SECRET", "").strip()
    if not key or not secret:
        return None, "Razorpay credentials are missing in .env"

    return razorpay.Client(auth=(key, secret)), None


def _place_order_from_snapshot(snapshot, order_status):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    subtotal = _to_decimal(snapshot["subtotal"])

    try:
        cursor.execute(
            "INSERT INTO orders (user_id, total_amount, status) VALUES (%s, %s, %s)",
            (session["user_id"], str(subtotal), order_status),
        )
        order_id = cursor.lastrowid

        for item in snapshot["items"]:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
            unit_price = _to_decimal(item["unit_price"])

            cursor.execute(
                "SELECT stock FROM products WHERE id = %s AND is_active = 1 FOR UPDATE",
                (product_id,),
            )
            product_row = cursor.fetchone()
            if not product_row:
                raise ValueError("One of the products is no longer available.")
            if int(product_row["stock"]) < quantity:
                raise ValueError("Insufficient stock for one or more items.")

            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, quantity, str(unit_price)),
            )
            cursor.execute(
                "UPDATE products SET stock = stock - %s WHERE id = %s",
                (quantity, product_id),
            )

        conn.commit()
        _invalidate_catalog_cache()
        return order_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def _complete_order_flow(order_id, success_message):
    _enqueue_post_order_task(order_id)
    session["cart"] = {}
    session.pop("checkout_snapshot", None)
    session.modified = True
    flash(success_message, "success")
    return redirect(url_for("checkout.order_detail", order_id=order_id))


@checkout_bp.route("/checkout")
@login_required
def checkout():
    items, subtotal = _get_checkout_cart()
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart.view_cart"))

    client, error = _get_razorpay_client()
    if error:
        flash(error, "danger")
        return redirect(url_for("cart.view_cart"))

    amount_paise = int((subtotal * 100).to_integral_value(rounding=ROUND_HALF_UP))
    receipt = f"shopmax_{session['user_id']}_{uuid4().hex[:8]}"
    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1,
    }

    try:
        razorpay_order = client.order.create(data=order_data)
    except Exception:
        flash("Unable to create Razorpay order. Please try again.", "danger")
        return redirect(url_for("cart.view_cart"))

    session["checkout_snapshot"] = {
        "razorpay_order_id": razorpay_order["id"],
        "subtotal": str(subtotal),
        "items": [
            {
                "product_id": item["id"],
                "quantity": item["quantity"],
                "unit_price": str(item["unit_price"]),
            }
            for item in items
        ],
    }
    session.modified = True

    user = query_one("SELECT name, email FROM users WHERE id = %s", (session["user_id"],))

    return render_template(
        "checkout.html",
        items=items,
        subtotal=subtotal,
        razorpay_key=current_app.config["RAZORPAY_KEY"],
        razorpay_order_id=razorpay_order["id"],
        amount_paise=amount_paise,
        user_name=user["name"] if user else session.get("user_name", "Customer"),
        user_email=user["email"] if user else "",
    )


@checkout_bp.route("/checkout/verify", methods=["POST"])
@login_required
def verify_payment():
    posted_order_id = request.form.get("razorpay_order_id", "").strip()
    payment_id = request.form.get("razorpay_payment_id", "").strip()
    signature = request.form.get("razorpay_signature", "").strip()

    snapshot = session.get("checkout_snapshot")
    if not snapshot:
        flash("Checkout session expired. Please try again.", "warning")
        return redirect(url_for("cart.view_cart"))

    if posted_order_id != snapshot.get("razorpay_order_id"):
        flash("Order mismatch detected. Please retry checkout.", "danger")
        return redirect(url_for("cart.view_cart"))

    client, error = _get_razorpay_client()
    if error:
        flash(error, "danger")
        return redirect(url_for("cart.view_cart"))

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": posted_order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        )
    except Exception:
        flash("Payment signature verification failed.", "danger")
        return redirect(url_for("checkout.checkout"))

    try:
        order_id = _place_order_from_snapshot(snapshot, "PAID")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("cart.view_cart"))
    except Exception:
        flash("Payment captured but order save failed. Contact support with payment ID.", "danger")
        return redirect(url_for("cart.view_cart"))

    return _complete_order_flow(order_id, "Payment successful. Your order has been placed.")


@checkout_bp.route("/checkout/cod", methods=["POST"])
@login_required
def cod_checkout():
    snapshot = session.get("checkout_snapshot")
    if not snapshot:
        flash("Checkout session expired. Please open checkout again.", "warning")
        return redirect(url_for("cart.view_cart"))

    try:
        order_id = _place_order_from_snapshot(snapshot, "COD_PENDING")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("cart.view_cart"))
    except Exception:
        flash("Could not place COD order. Please try again.", "danger")
        return redirect(url_for("checkout.checkout"))

    return _complete_order_flow(order_id, "COD order placed successfully.")


@checkout_bp.route("/orders")
@login_required
def orders():
    rows = query_all(
        """
        SELECT o.id, o.total_amount, o.status, o.created_at, COUNT(oi.id) AS item_count
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        WHERE o.user_id = %s
        GROUP BY o.id
        ORDER BY o.created_at DESC
        """,
        (session["user_id"],),
    )
    return render_template("orders.html", orders=rows, cancellable_statuses=CANCELLABLE_STATUSES)


@checkout_bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order = query_one(
        """
        SELECT id, total_amount, status, created_at
        FROM orders
        WHERE id = %s AND user_id = %s
        """,
        (order_id, session["user_id"]),
    )
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("checkout.orders"))

    items = query_all(
        """
        SELECT oi.quantity, oi.unit_price, p.name, p.brand
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = %s
        """,
        (order_id,),
    )

    return render_template(
        "order_detail.html",
        order=order,
        items=items,
        cancellable_statuses=CANCELLABLE_STATUSES,
    )


@checkout_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order(order_id):
    next_url = request.form.get("next", "").strip()
    redirect_target = next_url if next_url.startswith("/") else url_for("checkout.orders")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id, status FROM orders WHERE id = %s AND user_id = %s FOR UPDATE",
            (order_id, session["user_id"]),
        )
        order = cursor.fetchone()
        if not order:
            flash("Order not found.", "danger")
            conn.rollback()
            return redirect(redirect_target)

        if order["status"] == "CANCELLED":
            flash("Order is already cancelled.", "info")
            conn.rollback()
            return redirect(redirect_target)

        if order["status"] not in CANCELLABLE_STATUSES:
            flash("This order cannot be cancelled now.", "warning")
            conn.rollback()
            return redirect(redirect_target)

        cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
        items = cursor.fetchall()

        for item in items:
            cursor.execute(
                "UPDATE products SET stock = stock + %s WHERE id = %s",
                (int(item["quantity"]), int(item["product_id"])),
            )

        cursor.execute("UPDATE orders SET status = %s WHERE id = %s", ("CANCELLED", order_id))
        conn.commit()
        _invalidate_catalog_cache()
        flash("Order cancelled successfully.", "success")
    except Exception:
        conn.rollback()
        flash("Unable to cancel order right now.", "danger")
    finally:
        cursor.close()

    return redirect(redirect_target)


@checkout_bp.route("/orders/<int:order_id>/invoice")
@login_required
def download_invoice(order_id):
    order = query_one(
        """
        SELECT o.id, o.total_amount, o.status, o.created_at, u.name, u.email
        FROM orders o
        JOIN users u ON u.id = o.user_id
        WHERE o.id = %s AND o.user_id = %s
        """,
        (order_id, session["user_id"]),
    )
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("checkout.orders"))

    items = query_all(
        """
        SELECT oi.quantity, oi.unit_price, p.name, p.brand
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = %s
        """,
        (order_id,),
    )

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    y = page_height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(45, y, "SHOP MAX - INVOICE")

    y -= 28
    pdf.setFont("Helvetica", 11)
    pdf.drawString(45, y, f"Order ID: {order['id']}")
    y -= 18
    pdf.drawString(45, y, f"Date: {order['created_at']}")
    y -= 18
    pdf.drawString(45, y, f"Customer: {order['name']} ({order['email']})")
    y -= 18
    pdf.drawString(45, y, f"Order Status: {order['status']}")

    y -= 30
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(45, y, "Item")
    pdf.drawString(290, y, "Qty")
    pdf.drawString(350, y, "Price")
    pdf.drawString(450, y, "Total")

    y -= 14
    pdf.line(45, y, 545, y)
    y -= 20

    total = Decimal("0.00")
    pdf.setFont("Helvetica", 10)

    for item in items:
        quantity = int(item["quantity"])
        price = _to_decimal(item["unit_price"])
        line_total = (price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += line_total

        if y < 80:
            pdf.showPage()
            y = page_height - 50
            pdf.setFont("Helvetica", 10)

        item_label = f"{item['name']} ({item['brand']})"
        pdf.drawString(45, y, item_label[:42])
        pdf.drawString(290, y, str(quantity))
        pdf.drawRightString(425, y, f"INR {price}")
        pdf.drawRightString(540, y, f"INR {line_total}")
        y -= 18

    y -= 8
    pdf.line(45, y, 545, y)
    y -= 20
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(540, y, f"Grand Total: INR {total.quantize(Decimal('0.01'))}")

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"shopmax_invoice_{order_id}.pdf",
        mimetype="application/pdf",
    )
