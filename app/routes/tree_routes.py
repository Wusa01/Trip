from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Person
from app.services.tree_service import get_local_subtree, get_lineage_report, get_branch_report
from app.services.person_service import search_persons

tree_bp = Blueprint("tree", __name__, url_prefix="/tree")


@tree_bp.route("/<int:person_id>", methods=["GET"])
@login_required
def tree_view(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        return "الشخص غير موجود", 404
    return render_template("tree_view.html", person=person)


@tree_bp.route("/api/<int:person_id>/subtree", methods=["GET"])
@login_required
def api_subtree(person_id):
    up_levels = request.args.get("up", default=2, type=int)
    down_levels = request.args.get("down", default=2, type=int)

    try:
        subtree = get_local_subtree(person_id, up_levels=up_levels, down_levels=down_levels)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify(subtree)


@tree_bp.route("/api/search", methods=["GET"])
@login_required
def api_tree_search():
    """بحث سريع داخل شاشة الشجرة للانتقال المباشر لأي شخص آخر دون مغادرة الصفحة"""
    query_text = request.args.get("q", "").strip()
    if not query_text:
        return jsonify([])

    only_approved = current_user.role not in ("admin", "researcher")
    results = search_persons(query_text, only_approved=only_approved)

    return jsonify([
        {"id": r["person"].id, "full_name": r["person"].full_name, "public_id": r["person"].public_id}
        for r in results[:8]
    ])


@tree_bp.route("/api/<int:person_id>/lineage", methods=["GET"])
@login_required
def api_lineage(person_id):
    try:
        chain = get_lineage_report(person_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify({"chain": chain})


@tree_bp.route("/api/<int:person_id>/branch-report", methods=["GET"])
@login_required
def api_branch_report(person_id):
    try:
        report = get_branch_report(person_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify(report)
