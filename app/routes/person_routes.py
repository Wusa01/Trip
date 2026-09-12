from flask import Blueprint, request, jsonify, render_template, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Person, Tribe
from app.services.person_service import (
    create_person,
    create_person_full,
    add_spouse_to_person,
    link_existing_spouse,
    add_parents_to_person,
    add_child_to_couple,
    remove_child_from_couple,
    merge_persons,
    update_person,
    approve_person,
    search_persons,
    search_persons_by_gender,
    get_visible_person_data,
    get_parental_info,
)
from app.services.relation_service import get_spouses_with_children, get_children

person_bp = Blueprint("person", __name__, url_prefix="/persons")


def _tribe_names():
    return sorted({t.tribe_name for t in Tribe.query.all()})


# ---------------------------------------------------------------------------
# صفحات العرض (HTML)
# ---------------------------------------------------------------------------

@person_bp.route("/new", methods=["GET"])
@login_required
def new_person_form():
    return render_template("person_form.html", tribe_names=_tribe_names())


@person_bp.route("/<int:person_id>", methods=["GET"])
@login_required
def view_person(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)

    if person.status != "approved" and current_user.role not in ("admin", "researcher"):
        abort(404)

    data = get_visible_person_data(person, current_user.role)
    return render_template("person_card.html", person=person, data=data)


@person_bp.route("/<int:person_id>/edit", methods=["GET"])
@login_required
def edit_person_form(person_id):
    if current_user.role not in ("admin", "researcher"):
        abort(403)

    person = db.session.get(Person, person_id)
    if not person:
        abort(404)

    return render_template("edit_person_form.html", person=person, tribe_names=_tribe_names())


@person_bp.route("/<int:person_id>/add-spouse", methods=["GET"])
@login_required
def add_spouse_form(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    return render_template("add_spouse_form.html", person=person, tribe_names=_tribe_names())


@person_bp.route("/<int:person_id>/add-parents", methods=["GET"])
@login_required
def add_parents_form(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    return render_template("add_parents_form.html", person=person, tribe_names=_tribe_names())


@person_bp.route("/merge", methods=["GET"])
@login_required
def merge_page():
    if current_user.role != "admin":
        abort(403)
    return render_template("merge_persons.html")


@person_bp.route("/search", methods=["GET"])
@login_required
def search_page():
    query_text = request.args.get("q", "").strip()
    results = []
    if query_text:
        only_approved = current_user.role not in ("admin", "researcher")
        results = search_persons(query_text, only_approved=only_approved)
    return render_template("search.html", query_text=query_text, results=results)


# ---------------------------------------------------------------------------
# نقاط API
# ---------------------------------------------------------------------------

@person_bp.route("/api/create", methods=["POST"])
@login_required
def api_create_person():
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية إضافة أشخاص"}), 403

    form = request.form
    data = {
        "full_name": form.get("full_name"),
        "gender": form.get("gender"),
        "tribe_name": form.get("tribe_name") or None,
        "birth_date": form.get("birth_date") or None,
        "birth_place": form.get("birth_place") or None,
        "death_date": form.get("death_date") or None,
        "marital_status": form.get("marital_status", "single"),
        "disambiguation_note": form.get("disambiguation_note") or None,
        "notes": form.get("notes") or None,
        "is_living": form.get("is_living", "true") == "true",
    }

    photo_file = request.files.get("photo")
    auto_approve = current_user.role == "admin"

    try:
        person = create_person(data, current_user.id, photo_file=photo_file, auto_approve=auto_approve)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": person.id, "public_id": person.public_id, "status": person.status}), 201


@person_bp.route("/api/create-full", methods=["POST"])
@login_required
def api_create_person_full():
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية إضافة أشخاص"}), 403

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "بيانات غير صالحة"}), 400

    auto_approve = current_user.role == "admin"

    try:
        person, children, spouses = create_person_full(payload, current_user.id, auto_approve=auto_approve)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "id": person.id,
        "public_id": person.public_id,
        "children_created": len(children),
        "spouses_created": len(spouses),
    }), 201


@person_bp.route("/api/<int:person_id>/add-spouse", methods=["POST"])
@login_required
def api_add_spouse(person_id):
    """إضافة زوجة/زوج جديد (لم يكن مسجَّلاً من قبل)"""
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية الإضافة"}), 403

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "بيانات غير صالحة"}), 400

    auto_approve = current_user.role == "admin"

    try:
        spouse, children = add_spouse_to_person(person_id, payload, current_user.id, auto_approve=auto_approve)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "spouse_id": spouse.id,
        "spouse_public_id": spouse.public_id,
        "children_created": len(children),
    }), 201


@person_bp.route("/api/<int:person_id>/link-spouse", methods=["POST"])
@login_required
def api_link_existing_spouse(person_id):
    """
    ربط زوج/زوجة موجود مسبقاً في السجل — للحالات الاستثنائية مثل زواج
    الأخ من زوجة أخيه المتوفى، حيث كلا الطرفين مسجَّل بالفعل.
    """
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية الإضافة"}), 403

    spouse_id = request.form.get("spouse_id", type=int)
    marriage_date = request.form.get("marriage_date") or None

    if not spouse_id:
        return jsonify({"error": "يجب اختيار الشخص المسجَّل"}), 400

    try:
        marriage, person, spouse = link_existing_spouse(
            person_id, spouse_id, current_user.id, marriage_date=marriage_date,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "marriage_id": marriage.id,
        "spouse_id": spouse.id,
        "spouse_public_id": spouse.public_id,
    }), 201


@person_bp.route("/api/search-for-spouse", methods=["GET"])
@login_required
def api_search_for_spouse():
    """
    بحث مقيَّد بالجنس المعاكس لشخص محدد، لاستخدامه عند اختيار
    زوج/زوجة موجود مسبقاً في السجل بدل إنشاء شخص جديد.
    """
    query_text = request.args.get("q", "").strip()
    for_person_id = request.args.get("for_person_id", type=int)

    if not query_text or not for_person_id:
        return jsonify([])

    person = db.session.get(Person, for_person_id)
    if not person:
        return jsonify([])

    required_gender = "female" if person.gender == "male" else "male"
    only_approved = current_user.role not in ("admin", "researcher")

    results = search_persons_by_gender(
        query_text, required_gender, exclude_id=for_person_id, only_approved=only_approved,
    )

    return jsonify([
        {
            "id": p.id,
            "public_id": p.public_id,
            "full_name": p.full_name,
            "tribe": p.tribe.tribe_name if p.tribe else None,
            "marital_status": p.marital_status,
        }
        for p in results
    ])


@person_bp.route("/api/<int:person_id>/add-parents", methods=["POST"])
@login_required
def api_add_parents(person_id):
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية الإضافة"}), 403

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "بيانات غير صالحة"}), 400

    auto_approve = current_user.role == "admin"

    try:
        father, mother = add_parents_to_person(
            person_id, payload.get("father"), payload.get("mother"),
            current_user.id, auto_approve=auto_approve,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "father_id": father.id if father else None,
        "mother_id": mother.id if mother else None,
    }), 201


@person_bp.route("/api/<int:person_id>/spouse/<int:spouse_id>/add-child", methods=["POST"])
@login_required
def api_add_child_to_couple(person_id, spouse_id):
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية الإضافة"}), 403

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "بيانات غير صالحة"}), 400

    auto_approve = current_user.role == "admin"

    try:
        child = add_child_to_couple(person_id, spouse_id, payload, current_user.id, auto_approve=auto_approve)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"child_id": child.id, "child_public_id": child.public_id}), 201


@person_bp.route("/api/<int:person_id>/spouse/<int:spouse_id>/child/<int:child_id>/remove", methods=["POST"])
@login_required
def api_remove_child_from_couple(person_id, spouse_id, child_id):
    if current_user.role != "admin":
        return jsonify({"error": "الحذف للمدير فقط"}), 403

    try:
        remove_child_from_couple(person_id, spouse_id, child_id, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"status": "removed"})


@person_bp.route("/api/merge-preview", methods=["GET"])
@login_required
def api_merge_preview():
    if current_user.role != "admin":
        return jsonify({"error": "غير مصرح"}), 403

    person_id = request.args.get("id", type=int)
    person = db.session.get(Person, person_id)
    if not person:
        return jsonify({"error": "الشخص غير موجود"}), 404

    parental = get_parental_info(person_id)
    spouses = get_spouses_with_children(person_id)
    children = get_children(person_id)

    return jsonify({
        "id": person.id,
        "public_id": person.public_id,
        "full_name": person.full_name,
        "gender": person.gender,
        "tribe": person.tribe.tribe_name if person.tribe else None,
        "father_name": parental["father_name"],
        "mother_name": parental["mother_name"],
        "spouses_count": len(spouses),
        "children_count": len(children),
        "status": person.status,
    })


@person_bp.route("/api/merge", methods=["POST"])
@login_required
def api_merge_persons():
    if current_user.role != "admin":
        return jsonify({"error": "الدمج للمدير فقط"}), 403

    keep_id = request.form.get("keep_id", type=int)
    duplicate_id = request.form.get("duplicate_id", type=int)

    if not keep_id or not duplicate_id:
        return jsonify({"error": "يجب اختيار السجلين"}), 400

    try:
        keep = merge_persons(keep_id, duplicate_id, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"kept_id": keep.id, "kept_public_id": keep.public_id})


@person_bp.route("/api/<int:person_id>/update", methods=["POST"])
@login_required
def api_update_person(person_id):
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية التعديل"}), 403

    form = request.form
    data = {k: v for k, v in {
        "full_name": form.get("full_name"),
        "gender": form.get("gender"),
        "tribe_name": form.get("tribe_name"),
        "birth_date": form.get("birth_date") or None,
        "birth_place": form.get("birth_place") or None,
        "death_date": form.get("death_date") or None,
        "marital_status": form.get("marital_status"),
        "disambiguation_note": form.get("disambiguation_note"),
        "notes": form.get("notes"),
        "is_living": (form.get("is_living") == "true") if form.get("is_living") is not None else None,
    }.items() if v is not None}

    photo_file = request.files.get("photo")

    try:
        person = update_person(person_id, data, current_user.id, photo_file=photo_file)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": person.id, "status": "updated"})


@person_bp.route("/api/<int:person_id>/approve", methods=["POST"])
@login_required
def api_approve_person(person_id):
    if current_user.role != "admin":
        return jsonify({"error": "الاعتماد للمدير فقط"}), 403

    try:
        person = approve_person(person_id, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": person.id, "status": person.status})


@person_bp.route("/api/search", methods=["GET"])
@login_required
def api_search():
    query_text = request.args.get("q", "").strip()
    if not query_text:
        return jsonify([])

    only_approved = current_user.role not in ("admin", "researcher")
    results = search_persons(query_text, only_approved=only_approved)

    return jsonify([
        {
            "id": r["person"].id,
            "public_id": r["person"].public_id,
            "full_name": r["person"].full_name,
            "disambiguation_note": r["person"].disambiguation_note,
            "tribe": r["person"].tribe.tribe_name if r["person"].tribe else None,
            "father_name": r["father_name"],
            "mother_name": r["mother_name"],
            "maternal_tribe": r["maternal_tribe"],
        }
        for r in results
    ])
