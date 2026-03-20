from collections import Counter
import re

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .db import execute, query_all, query_one
from .extensions import cache
from .utils import admin_required

store_bp = Blueprint("store", __name__)

VIEWED_PRODUCTS_KEY = "viewed_product_ids"
MAX_VIEWED_PRODUCTS = 20
IMAGE_SEARCH_STOPWORDS = {
    "img",
    "image",
    "photo",
    "camera",
    "screenshot",
    "scan",
    "picture",
    "captured",
    "upload",
}


def _record_product_view(product_id):
    history = session.get(VIEWED_PRODUCTS_KEY, [])
    if not isinstance(history, list):
        history = []

    history = [pid for pid in history if pid != product_id]
    history.insert(0, product_id)
    session[VIEWED_PRODUCTS_KEY] = history[:MAX_VIEWED_PRODUCTS]


def _extract_keywords_from_filename(filename):
    stem = filename.rsplit(".", 1)[0].lower()
    tokens = re.findall(r"[a-z0-9]+", stem)

    keywords = []
    seen = set()
    for token in tokens:
        if len(token) < 3 or token in IMAGE_SEARCH_STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        keywords.append(token)
    return keywords


def _build_products_query(search="", category="", min_price="", max_price=""):
    sql = """
        SELECT p.id, p.name, p.brand, p.price, p.stock, p.image_url, p.category_id, c.name AS category
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = 1
    """
    params = []

    if search:
        sql += " AND (p.name LIKE %s OR p.brand LIKE %s OR p.description LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like, like])
    if category:
        sql += " AND c.name = %s"
        params.append(category)
    if min_price:
        try:
            sql += " AND p.price >= %s"
            params.append(float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            sql += " AND p.price <= %s"
            params.append(float(max_price))
        except ValueError:
            pass

    sql += " ORDER BY p.created_at DESC"
    return sql, tuple(params)


def _get_ai_suggestions(limit=6, exclude_product_id=None):
    history = session.get(VIEWED_PRODUCTS_KEY, [])
    if not history:
        return []

    viewed_rows = query_all(
        """
        SELECT id, brand, category_id
        FROM products
        WHERE id IN ("""
        + ",".join(["%s"] * len(history))
        + ")",
        tuple(history),
    )
    if not viewed_rows:
        return []

    category_counts = Counter(row["category_id"] for row in viewed_rows)
    brand_counts = Counter(row["brand"] for row in viewed_rows)

    exclude_sql = ""
    params = []
    if exclude_product_id is not None:
        exclude_sql = " AND p.id != %s"
        params.append(exclude_product_id)

    candidates = query_all(
        """
        SELECT p.id, p.name, p.brand, p.price, p.stock, p.image_url, p.category_id, c.name AS category
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = 1
        """
        + exclude_sql
        + " ORDER BY p.created_at DESC",
        tuple(params),
    )

    scored = []
    for item in candidates:
        score = category_counts.get(item["category_id"], 0) * 3
        score += brand_counts.get(item["brand"], 0) * 2
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda row: row[0], reverse=True)

    seen_ids = set()
    results = []
    for _, item in scored:
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        results.append(item)
        if len(results) == limit:
            break

    return results


def _serialize_product(row):
    product = {
        "id": int(row["id"]),
        "name": row["name"],
        "brand": row.get("brand", ""),
        "price": float(row["price"]),
        "image_url": row.get("image_url") or "",
        "category": row.get("category", ""),
    }
    if "stock" in row:
        product["stock"] = int(row["stock"])
    if "description" in row:
        product["description"] = row.get("description") or ""
    return product


def _serialize_products(rows):
    return [_serialize_product(row) for row in rows]


def _storefront_routes():
    products_url = url_for("store.products")
    cart_url = url_for("cart.view_cart").rstrip("/")
    return {
        "home": url_for("store.home"),
        "products": products_url,
        "products_image_search": url_for("store.products_image_search"),
        "product_detail_template": products_url.rstrip("/") + "/__PRODUCT_ID__",
        "cart_add_template": cart_url + "/add/__PRODUCT_ID__",
    }


def _render_storefront(view, payload):
    return render_template(
        "storefront_react.html",
        storefront_data={
            "view": view,
            "payload": payload,
            "routes": _storefront_routes(),
            "assets": {
                "placeholder_image": url_for("static", filename="images/product-placeholder.svg"),
            },
        },
    )


@store_bp.route("/")
@cache.cached(timeout=120)
def home():
    featured = _serialize_products(
        query_all(
            """
        SELECT p.id, p.name, p.brand, p.price, p.image_url, c.name AS category
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = 1
        ORDER BY p.created_at DESC
        LIMIT 8
        """
        )
    )
    return _render_storefront("home", {"products": featured})


@store_bp.route("/products")
@cache.cached(timeout=120, query_string=True)
def products():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()

    sql, params = _build_products_query(search, category, min_price, max_price)
    items = _serialize_products(query_all(sql, params))
    categories = [row["name"] for row in query_all("SELECT name FROM categories ORDER BY name ASC")]

    return _render_storefront(
        "products",
        {
            "products": items,
            "categories": categories,
            "filters": {
                "q": search,
                "category": category,
                "min_price": min_price,
                "max_price": max_price,
            },
            "ai_suggestions": _serialize_products(_get_ai_suggestions(limit=6)),
            "image_search_used": False,
        },
    )


@store_bp.route("/products/image-search", methods=["POST"])
def products_image_search():
    image = request.files.get("search_image")
    if not image or not image.filename:
        flash("Take or upload an image to search products.", "warning")
        return redirect(url_for("store.products"))

    keywords = _extract_keywords_from_filename(image.filename)
    if not keywords:
        flash("Could not infer keywords from image name. Rename the file with product words and retry.", "warning")
        return redirect(url_for("store.products"))

    clauses = []
    params = []
    for word in keywords[:4]:
        like = f"%{word}%"
        clauses.append("(p.name LIKE %s OR p.brand LIKE %s OR p.description LIKE %s OR c.name LIKE %s)")
        params.extend([like, like, like, like])

    sql = (
        """
        SELECT p.id, p.name, p.brand, p.price, p.stock, p.image_url, p.category_id, c.name AS category
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = 1
        """
        + " AND ("
        + " OR ".join(clauses)
        + ") ORDER BY p.created_at DESC"
    )

    items = _serialize_products(query_all(sql, tuple(params)))
    categories = [row["name"] for row in query_all("SELECT name FROM categories ORDER BY name ASC")]

    flash(
        "Image search used keywords: " + ", ".join(keywords[:4]),
        "info",
    )

    return _render_storefront(
        "products",
        {
            "products": items,
            "categories": categories,
            "filters": {"q": " ".join(keywords[:4]), "category": "", "min_price": "", "max_price": ""},
            "ai_suggestions": _serialize_products(_get_ai_suggestions(limit=6)),
            "image_search_used": True,
        },
    )


@store_bp.route("/products/<int:product_id>")
@cache.cached(timeout=180)
def product_detail(product_id):
    item = query_one(
        """
        SELECT p.id, p.name, p.brand, p.description, p.price, p.stock, p.image_url,
               p.category_id, c.name AS category
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.id = %s AND p.is_active = 1
        """,
        (product_id,),
    )
    if not item:
        flash("Product not found.", "danger")
        return redirect(url_for("store.products"))

    _record_product_view(product_id)
    suggestions = _get_ai_suggestions(limit=4, exclude_product_id=product_id)

    return _render_storefront(
        "product_detail",
        {
            "product": _serialize_product(item),
            "ai_suggestions": _serialize_products(suggestions),
        },
    )


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
        cache.clear()
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
