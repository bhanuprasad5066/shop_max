from datetime import timedelta

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import execute, query_one

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _build_jwt_payload(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "is_admin": bool(user["is_admin"]),
    }


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        existing = query_one("SELECT id FROM users WHERE email = %s", (email,))
        if existing:
            flash("Email already exists. Please log in.", "warning")
            return redirect(url_for("auth.login"))

        password_hash = generate_password_hash(password)
        execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, password_hash),
        )
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = query_one(
            "SELECT id, name, email, password_hash, is_admin FROM users WHERE email = %s",
            (email,),
        )
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid credentials.", "danger")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["is_admin"] = bool(user["is_admin"])
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("store.home"))

    return render_template("login.html")


@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    user = query_one(
        "SELECT id, name, email, password_hash, is_admin FROM users WHERE email = %s",
        (email,),
    )
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    identity = str(user["id"])
    claims = {
        "name": user["name"],
        "email": user["email"],
        "is_admin": bool(user["is_admin"]),
    }
    access_token = create_access_token(
        identity=identity,
        additional_claims=claims,
        expires_delta=timedelta(seconds=int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"])),
    )
    refresh_token = create_refresh_token(
        identity=identity,
        additional_claims=claims,
        expires_delta=timedelta(seconds=int(current_app.config["JWT_REFRESH_TOKEN_EXPIRES"])),
    )

    return jsonify(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": _build_jwt_payload(user),
        }
    )


@auth_bp.route("/api/refresh", methods=["POST"])
@jwt_required(refresh=True)
def api_refresh():
    user_id = int(get_jwt_identity())
    user = query_one(
        "SELECT id, name, email, is_admin FROM users WHERE id = %s",
        (user_id,),
    )
    if not user:
        return jsonify({"error": "user not found"}), 404

    claims = {
        "name": user["name"],
        "email": user["email"],
        "is_admin": bool(user["is_admin"]),
    }
    access_token = create_access_token(
        identity=str(user["id"]),
        additional_claims=claims,
        expires_delta=timedelta(seconds=int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"])),
    )
    return jsonify({"access_token": access_token})


@auth_bp.route("/api/me", methods=["GET"])
@jwt_required()
def api_me():
    user_id = int(get_jwt_identity())
    user = query_one(
        "SELECT id, name, email, is_admin FROM users WHERE id = %s",
        (user_id,),
    )
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify({"user": _build_jwt_payload(user)})


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("store.home"))
