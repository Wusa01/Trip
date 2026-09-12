from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Person, Relation, Marriage
from app.services.relation_service import (
    add_parent_child_relation,
    approve_relation,
    reject_relation,
    delete_relation,
    get_parents,
    get_parent_relations,
    get_children,
    get_siblings,
    get_mother,
    get_father,
    get_spouses_with_children,
    get_relation_label,
    get_child_label,
    create_marriage as create_marriage_service,
    _log_audit,
)

relation_bp = Blueprint("relation", __name__, url_prefix="/relations")


# ---------------------------------------------------------------------------
# علاقات الأبوة
# ---------------------------------------------------------------------------

@relation_bp.route("/api/add-parent-child", methods=["POST"])
@login_required
def api_add_parent_child():
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية إضافة علاقات"}), 403

    parent_id = request.form.get("parent_id", type=int)
    child_id = request.form.get("child_id", type=int)

    if not parent_id or not child_id:
        return jsonify({"error": "يجب اختيار الأب/الأم والابن/الابنة"}), 400

    if not db.session.get(Person, parent_id) or not db.session.get(Person, child_id):
        return jsonify({"error": "أحد الأشخاص غير موجود"}), 404

    auto_approve = current_user.role == "admin"

    try:
        relation = add_parent_child_relation(parent_id, child_id, current_user.id, auto_approve=auto_approve)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": relation.id, "status": relation.status}), 201


@relation_bp.route("/pending", methods=["GET"])
@login_required
def pending_page():
    if current_user.role != "admin":
        return "غير مصرح", 403

    pending_relations = Relation.query.filter_by(status="pending").all()
    return render_template("pending_review.html", pending_relations=pending_relations)


@relation_bp.route("/api/<int:relation_id>/approve", methods=["POST"])
@login_required
def api_approve_relation(relation_id):
    if current_user.role != "admin":
        return jsonify({"error": "الاعتماد للمدير فقط"}), 403

    try:
        relation = approve_relation(relation_id, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": relation.id, "status": relation.status})


@relation_bp.route("/api/<int:relation_id>/reject", methods=["POST"])
@login_required
def api_reject_relation(relation_id):
    if current_user.role != "admin":
        return jsonify({"error": "الرفض للمدير فقط"}), 403

    reason = request.form.get("reason", "")

    try:
        relation = reject_relation(relation_id, current_user.id, reason=reason)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": relation.id, "status": relation.status})


@relation_bp.route("/api/<int:relation_id>/delete", methods=["POST"])
@login_required
def api_delete_relation(relation_id):
    """
    حذف رابط أبوة خاطئ (تصحيح: أب/أم أُدخل بالخطأ). للمدير فقط.
    بعد الحذف، استخدم شاشة "إضافة الوالدين" لإضافة الأب/الأم الصحيح.
    """
    if current_user.role != "admin":
        return jsonify({"error": "الحذف للمدير فقط"}), 403

    try:
        delete_relation(relation_id, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"status": "deleted"})


@relation_bp.route("/api/person/<int:person_id>/family", methods=["GET"])
@login_required
def api_person_family(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        return jsonify({"error": "الشخص غير موجود"}), 404

    parent_relations = get_parent_relations(person_id)
    father_relation = next((r for r in parent_relations if r.parent.gender == "male"), None)
    mother_relation = next((r for r in parent_relations if r.parent.gender == "female"), None)

    siblings = get_siblings(person_id)
    spouses_data = get_spouses_with_children(person_id)

    return jsonify({
        "father": {
            "id": father_relation.parent.id,
            "full_name": father_relation.parent.full_name,
            "relation_id": father_relation.id,
        } if father_relation else None,
        "mother": {
            "id": mother_relation.parent.id,
            "full_name": mother_relation.parent.full_name,
            "tribe": mother_relation.parent.tribe.tribe_name if mother_relation.parent.tribe else None,
            "relation_id": mother_relation.id,
        } if mother_relation else None,
        "siblings": [{"id": s.id, "public_id": s.public_id, "full_name": s.full_name} for s in siblings],
        "spouses": [
            {
                "id": item["spouse"].id,
                "public_id": item["spouse"].public_id,
                "full_name": item["spouse"].full_name,
                "tribe": item["spouse"].tribe.tribe_name if item["spouse"].tribe else None,
                "marriage_status": item["marriage_status"],
                "children": [
                    {"id": c.id, "public_id": c.public_id, "full_name": c.full_name, "gender": c.gender}
                    for c in item["children"]
                ],
            }
            for item in spouses_data
        ],
    })


# ---------------------------------------------------------------------------
# الزواج
# ---------------------------------------------------------------------------

@relation_bp.route("/api/marriage/create", methods=["POST"])
@login_required
def api_create_marriage():
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية إضافة زواج"}), 403

    husband_id = request.form.get("husband_id", type=int)
    wife_id = request.form.get("wife_id", type=int)
    marriage_date = request.form.get("marriage_date") or None

    husband = db.session.get(Person, husband_id) if husband_id else None
    wife = db.session.get(Person, wife_id) if wife_id else None

    if not husband or not wife:
        return jsonify({"error": "يجب اختيار الزوج والزوجة"}), 404
    if husband.gender != "male" or wife.gender != "female":
        return jsonify({"error": "تأكد من اختيار الزوج (ذكر) والزوجة (أنثى) بشكل صحيح"}), 400

    existing = Marriage.query.filter_by(husband_id=husband_id, wife_id=wife_id, status="current").first()
    if existing:
        return jsonify({"error": "يوجد بالفعل زواج قائم بين هذين الشخصين"}), 400

    marriage = create_marriage_service(husband_id, wife_id, current_user.id, marriage_date=marriage_date)
    return jsonify({"id": marriage.id, "status": marriage.status}), 201


@relation_bp.route("/api/marriage/<int:marriage_id>/divorce", methods=["POST"])
@login_required
def api_divorce_marriage(marriage_id):
    if current_user.role not in ("admin", "researcher"):
        return jsonify({"error": "لا تملك صلاحية تسجيل الطلاق"}), 403

    marriage = db.session.get(Marriage, marriage_id)
    if not marriage:
        return jsonify({"error": "سجل الزواج غير موجود"}), 404

    divorce_date = request.form.get("divorce_date") or None
    marriage.status = "divorced"
    marriage.divorce_date = divorce_date
    db.session.commit()

    _refresh_marital_status(marriage.husband_id)
    _refresh_marital_status(marriage.wife_id)

    _log_audit(current_user.id, "update", "marriages", marriage.id, "status=divorced")
    return jsonify({"id": marriage.id, "status": marriage.status})


def _refresh_marital_status(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        return

    still_married = Marriage.query.filter(
        db.or_(Marriage.husband_id == person_id, Marriage.wife_id == person_id),
        Marriage.status == "current",
    ).first()

    if still_married:
        person.marital_status = "married"
    elif person.death_date:
        person.marital_status = "widowed"
    else:
        person.marital_status = "divorced"

    db.session.commit()
