from flask import Blueprint, flash, redirect, render_template, session, url_for

from .db import query_one
from .utils import login_required

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")


def _get_cart():
    if "cart" not in session:
        session["cart"] = {}
    return session["cart"]


@cart_bp.route("/")
@login_required
def view_cart():
    cart = _get_cart()
    items = []
    subtotal = 0.0

    for product_id, qty in cart.items():
        item = query_one(
            "SELECT id, name, brand, price, image_url, stock FROM products WHERE id = %s AND is_active = 1",
            (int(product_id),),
        )
        if not item:
            continue
        qty = int(qty)
        line_total = qty * float(item["price"])
        subtotal += line_total
        item["quantity"] = qty
        item["line_total"] = line_total
        items.append(item)

    return render_template("cart.html", items=items, subtotal=subtotal)


@cart_bp.route("/add/<int:product_id>")
@login_required
def add_to_cart(product_id):
    item = query_one("SELECT id, stock FROM products WHERE id = %s AND is_active = 1", (product_id,))
    if not item:
        flash("Product not found.", "danger")
        return redirect(url_for("store.products"))

    cart = _get_cart()
    current_qty = int(cart.get(str(product_id), 0))
    if current_qty >= int(item["stock"]):
        flash("Stock limit reached.", "warning")
        return redirect(url_for("cart.view_cart"))

    cart[str(product_id)] = current_qty + 1
    session.modified = True
    flash("Added to cart.", "success")
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/remove/<int:product_id>")
@login_required
def remove_from_cart(product_id):
    cart = _get_cart()
    cart.pop(str(product_id), None)
    session.modified = True
    flash("Item removed.", "info")
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/clear")
@login_required
def clear_cart():
    session["cart"] = {}
    flash("Cart cleared.", "info")
    return redirect(url_for("cart.view_cart"))