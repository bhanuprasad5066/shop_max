from flask import Blueprint, flash, redirect, render_template, request, url_for

from .db import execute, query_all, query_one
from .utils import admin_required

store_bp = Blueprint("store", __name__)


@store_bp.route("/")
def home():
    featured = query_all(
        """
        SELECT p.id, p.name, p.brand, p.price, p.image_url, c.name AS category
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = 1
        ORDER BY p.created_at DESC
        LIMIT 8
        """
    )
    return render_template("index.html", products=featured)


@store_bp.route("/products")
def products():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()

    sql = """
        SELECT p.id, p.name, p.brand, p.price, p.stock, p.image_url, c.name AS category
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = 1
    """
    params = []

    if search:
        sql += " AND (p.name LIKE %s OR p.brand LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like])
    if category:
        sql += " AND c.name = %s"
        params.append(category)
    if min_price:
        sql += " AND p.price >= %s"
        params.append(float(min_price))
    if max_price:
        sql += " AND p.price <= %s"
        params.append(float(max_price))

    sql += " ORDER BY p.created_at DESC"

    items = query_all(sql, tuple(params))
    categories = query_all("SELECT name FROM categories ORDER BY name ASC")

    return render_template(
        "products.html",
        products=items,
        categories=categories,
        filters={
            "q": search,
            "category": category,
            "min_price": min_price,
            "max_price": max_price,
        },
    )


@store_bp.route("/products/<int:product_id>")
def product_detail(product_id):
    item = query_one(
        """
        SELECT p.id, p.name, p.brand, p.description, p.price, p.stock, p.image_url,
               c.name AS category
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.id = %s AND p.is_active = 1
        """,
        (product_id,),
    )
    if not item:
        flash("Product not found.", "danger")
        return redirect(url_for("store.products"))

    return render_template("product_detail.html", product=item)


@store_bp.route("/admin/products", methods=["GET", "POST"])
@admin_required
def admin_products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        brand = request.form.get("brand", "").strip()
        description = request.form.get("description", "").strip()
        price = float(request.form.get("price", "0"))
        stock = int(request.form.get("stock", "0"))
        category_id = int(request.form.get("category_id"))
        image_url = request.form.get("image_url", "").strip()

        if not name or not brand or price <= 0:
            flash("Enter valid product details.", "danger")
            return redirect(url_for("store.admin_products"))

        execute(
            """
            INSERT INTO products (name, brand, description, price, stock, category_id, image_url, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
            """,
            (name, brand, description, price, stock, category_id, image_url),
        )
        flash("Product added.", "success")
        return redirect(url_for("store.admin_products"))

    items = query_all(
        """
        SELECT p.id, p.name, p.brand, p.price, p.stock, c.name AS category
        FROM products p
        JOIN categories c ON c.id = p.category_id
        ORDER BY p.created_at DESC
        """
    )
    categories = query_all("SELECT id, name FROM categories ORDER BY name")
    return render_template("admin_products.html", products=items, categories=categories)