from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user

from app.services.relationship_finder_service import find_relationship
from app.services.person_service import search_persons

relationship_bp = Blueprint("relationship", __name__, url_prefix="/relationship")


@relationship_bp.route("/", methods=["GET"])
@login_required
def relationship_page():
    return render_template("relationship_finder.html")


@relationship_bp.route("/api/search", methods=["GET"])
@login_required
def api_person_search():
    """بحث مصغَّر لاختيار الشخصين — نفس بحث الشجرة"""
    query_text = request.args.get("q", "").strip()
    if not query_text:
        return jsonify([])

    only_approved = current_user.role not in ("admin", "researcher")
    results = search_persons(query_text, only_approved=only_approved)

    return jsonify([
        {"id": r["person"].id, "full_name": r["person"].full_name, "public_id": r["person"].public_id}
        for r in results[:8]
    ])


@relationship_bp.route("/api/find", methods=["GET"])
@login_required
def api_find_relationship():
    person_a_id = request.args.get("a", type=int)
    person_b_id = request.args.get("b", type=int)

    if not person_a_id or not person_b_id:
        return jsonify({"error": "يجب اختيار الشخصين"}), 400

    try:
        result = find_relationship(person_a_id, person_b_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result)
