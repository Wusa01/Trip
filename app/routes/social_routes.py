from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user

from app.models import Tribe
from app.services.social_service import create_social_entry, list_social_entries, update_social_link
from app.services.person_service import search_persons

social_bp = Blueprint("social", __name__, url_prefix="/social")


def _tribe_names():
    return sorted({t.tribe_name for t in Tribe.query.all()})


# ---------------------------------------------------------------------------
# صفحات العرض (HTML)
# ---------------------------------------------------------------------------

@social_bp.route("/", methods=["GET"])
@login_required
def social_page():
    entry_type = request.args.get("type") or None
    if entry_type not in ("friend", "neighbor", None):
        entry_type = None

    only_approved = current_user.role not in ("admin", "researcher")
    entries = list_social_entries(entry_type=entry_type, only_approved=only_approved)
    return render_template("social.html", entries=entries, entry_type=entry_type)


@social_bp.route("/new", methods=["GET"])
@login_required
def new_social_form():
    if current_user.role not in ("admin", "researcher"):
        abort(403)

    entry_type = request.args.get("type", "friend")
    if entry_type not in ("friend", "neighbor"):
        entry_type = "friend"

    return render_template("social_form.html", tribe_names=_tribe_names(), entry_type=entry_type)


# ---------------------------------------------------------------------------
# نقاط API
# ---------------------------------------------------------------------------

@social_bp.route("/api/search-tribe-person", methods=["GET"])
@login_required
def api_search_tribe_person():
    """بحث عن فرد من العشيرة لربطه بصديق/جار (مثلاً: هذا صديق لفلان)"""
    query_text = request.args.get("q", "").strip()
    if not query_text:
        return jsonify([])

    only_approved = current_user.role not in ("admin", "researcher")
    results = search_persons(query_text, only_approved=only_approved)

    return jsonify([
        {
            "id": r["person"].id,
            "full_name": r["person"].full_name,
            "public_id": r["person"].public_id,
            "tribe": r["person"].tribe.tribe_name if r["person"].tribe else None,
        }
        for r in results[:8]
    ])


@social_bp.route("/api/create", methods=["POST"])
@login_required
def api_create_social():
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية الإضافة"}), 403

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "بيانات غير صالحة"}), 400

    entry_type = payload.get("entry_type")
    linked_person_id = payload.get("linked_person_id")
    link_note = payload.get("link_note")
    auto_approve = current_user.role == "admin"

    try:
        person, children, spouses = create_social_entry(
            payload, entry_type, current_user.id,
            linked_person_id=linked_person_id, link_note=link_note,
            auto_approve=auto_approve,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "id": person.id,
        "public_id": person.public_id,
        "children_created": len(children),
        "spouses_created": len(spouses),
    }), 201


@social_bp.route("/api/<int:person_id>/link", methods=["POST"])
@login_required
def api_update_link(person_id):
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية التعديل"}), 403

    payload = request.get_json(silent=True) or {}
    linked_person_id = payload.get("linked_person_id")
    link_note = payload.get("link_note")

    try:
        update_social_link(person_id, linked_person_id, link_note, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"ok": True})
