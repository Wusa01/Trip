from flask import Blueprint, request, jsonify, render_template, abort
from flask_login import login_required, current_user

from app.services.tribe_service import (
    list_tribes_with_counts,
    create_tribe,
    update_tribe,
    delete_tribe,
)

tribe_bp = Blueprint("tribe", __name__, url_prefix="/tribes")


# ---------------------------------------------------------------------------
# صفحة العرض (HTML) — للمدير فقط
# ---------------------------------------------------------------------------

@tribe_bp.route("", methods=["GET"])
@login_required
def tribes_page():
    if current_user.role != "admin":
        abort(403)

    rows = list_tribes_with_counts()
    return render_template("tribes.html", rows=rows)


# ---------------------------------------------------------------------------
# API: إنشاء / تعديل / حذف
# ---------------------------------------------------------------------------

@tribe_bp.route("/api/create", methods=["POST"])
@login_required
def api_create_tribe():
    if current_user.role != "admin":
        return jsonify({"error": "إضافة عشيرة للمدير فقط"}), 403

    tribe_name = request.form.get("tribe_name", "")
    branch_name = request.form.get("branch_name", "")

    try:
        tribe = create_tribe(tribe_name, branch_name, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "id": tribe.id,
        "tribe_name": tribe.tribe_name,
        "branch_name": tribe.branch_name,
        "person_count": 0,
    }), 201


@tribe_bp.route("/api/<int:tribe_id>/update", methods=["POST"])
@login_required
def api_update_tribe(tribe_id):
    if current_user.role != "admin":
        return jsonify({"error": "تعديل عشيرة للمدير فقط"}), 403

    tribe_name = request.form.get("tribe_name", "")
    branch_name = request.form.get("branch_name", "")

    try:
        tribe = update_tribe(tribe_id, tribe_name, branch_name, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "id": tribe.id,
        "tribe_name": tribe.tribe_name,
        "branch_name": tribe.branch_name,
    })


@tribe_bp.route("/api/<int:tribe_id>/delete", methods=["POST"])
@login_required
def api_delete_tribe(tribe_id):
    if current_user.role != "admin":
        return jsonify({"error": "حذف عشيرة للمدير فقط"}), 403

    try:
        delete_tribe(tribe_id, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": tribe_id, "status": "deleted"})
