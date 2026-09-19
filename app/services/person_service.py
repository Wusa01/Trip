import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app

from app.extensions import db
from app.models import Person, Tribe, Marriage, Relation, Closure
from app.services.relation_service import (
    ensure_self_closure,
    add_parent_child_relation,
    remove_parent_child_relation,
    create_marriage,
    get_mother,
    get_father,
    rebuild_closure_table,
    _log_audit,
)


# ---------------------------------------------------------------------------
# العشائر: مدخل حر، إيجاد أو إنشاء تلقائي
# ---------------------------------------------------------------------------

def get_or_create_tribe(tribe_name, branch_name=None):
    tribe_name = (tribe_name or "").strip()
    if not tribe_name:
        return None

    branch_name = (branch_name or "").strip() or None

    tribe = Tribe.query.filter_by(tribe_name=tribe_name, branch_name=branch_name).first()
    if tribe:
        return tribe

    tribe = Tribe(tribe_name=tribe_name, branch_name=branch_name)
    db.session.add(tribe)
    db.session.commit()
    return tribe


# ---------------------------------------------------------------------------
# توليد المعرف العام
# ---------------------------------------------------------------------------

def generate_public_id():
    while True:
        candidate = "T-" + uuid.uuid4().hex[:8].upper()
        if not Person.query.filter_by(public_id=candidate).first():
            return candidate


# ---------------------------------------------------------------------------
# رفع الصور
# ---------------------------------------------------------------------------

def _allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def save_person_photo(file_storage, public_id):
    if not file_storage or file_storage.filename == "":
        return None

    if not _allowed_file(file_storage.filename):
        raise ValueError("صيغة الصورة غير مدعومة (png, jpg, jpeg فقط)")

    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    filename = secure_filename(f"{public_id}.{ext}")
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    full_path = os.path.join(upload_folder, filename)

    file_storage.save(full_path)
    return f"uploads/{filename}"


# ---------------------------------------------------------------------------
# إنشاء / تعديل شخص واحد
# ---------------------------------------------------------------------------

def create_person(data, created_by_id, photo_file=None, auto_approve=False):
    if not data.get("full_name") or not data.get("gender"):
        raise ValueError("الاسم الكامل والجنس حقلان إلزاميان")

    tribe_id = data.get("tribe_id")
    if not tribe_id and data.get("tribe_name"):
        tribe = get_or_create_tribe(data["tribe_name"], data.get("tribe_branch"))
        tribe_id = tribe.id if tribe else None

    public_id = generate_public_id()

    person = Person(
        public_id=public_id,
        full_name=data["full_name"].strip(),
        gender=data["gender"],
        tribe_id=tribe_id,
        birth_date=data.get("birth_date"),
        birth_place=data.get("birth_place"),
        death_date=data.get("death_date"),
        marital_status=data.get("marital_status", "single"),
        disambiguation_note=data.get("disambiguation_note"),
        notes=data.get("notes"),
        is_living=data.get("is_living", True),
        status="approved" if auto_approve else "pending",
        person_type=data.get("person_type", "family"),
        created_by=created_by_id,
    )

    db.session.add(person)
    db.session.commit()

    ensure_self_closure(person.id)

    if photo_file:
        try:
            photo_path = save_person_photo(photo_file, public_id)
            person.photo_path = photo_path
            db.session.commit()
        except ValueError:
            pass

    _log_audit(created_by_id, "create", "persons", person.id, f"public_id={public_id}")
    return person


def update_person(person_id, data, updated_by_id, photo_file=None):
    person = db.session.get(Person, person_id)
    if not person:
        raise ValueError("الشخص غير موجود")

    if data.get("tribe_name"):
        tribe = get_or_create_tribe(data["tribe_name"], data.get("tribe_branch"))
        person.tribe_id = tribe.id if tribe else person.tribe_id

    for field in ("full_name", "gender", "birth_date", "birth_place",
                  "death_date", "marital_status", "disambiguation_note",
                  "notes", "is_living"):
        if field in data:
            setattr(person, field, data[field])

    person.updated_at = datetime.utcnow()

    if photo_file:
        try:
            person.photo_path = save_person_photo(photo_file, person.public_id)
        except ValueError:
            pass

    db.session.commit()
    _log_audit(updated_by_id, "update", "persons", person.id, "")
    return person


def approve_person(person_id, approver_id):
    person = db.session.get(Person, person_id)
    if not person:
        raise ValueError("الشخص غير موجود")
    person.status = "approved"
    db.session.commit()
    _log_audit(approver_id, "approve", "persons", person.id, "")
    return person


# ---------------------------------------------------------------------------
# إنشاء شامل: شخص + زوجات + أبناء كل زوجة تحديداً (عند الإضافة الأولى)
# ---------------------------------------------------------------------------

def create_person_full(data, created_by_id, auto_approve=False):
    main_person = create_person(data, created_by_id, auto_approve=auto_approve)
    created_children = []
    created_spouses = []

    def add_spouse_with_children(spouse_data, marriage_status):
        if not spouse_data.get("full_name"):
            return

        spouse_gender = "female" if main_person.gender == "male" else "male"
        spouse = create_person(
            {
                "full_name": spouse_data["full_name"],
                "gender": spouse_gender,
                "tribe_name": spouse_data.get("tribe_name"),
                "tribe_branch": spouse_data.get("tribe_branch"),
                "marital_status": "married" if marriage_status == "current" else "divorced",
            },
            created_by_id, auto_approve=auto_approve,
        )

        husband_id = main_person.id if main_person.gender == "male" else spouse.id
        wife_id = spouse.id if main_person.gender == "male" else main_person.id
        create_marriage(husband_id, wife_id, created_by_id, status=marriage_status)
        created_spouses.append(spouse)

        for child_data in spouse_data.get("children", []):
            if not child_data.get("full_name"):
                continue
            child = create_person(
                {"full_name": child_data["full_name"], "gender": child_data.get("gender", "male")},
                created_by_id, auto_approve=auto_approve,
            )
            add_parent_child_relation(main_person.id, child.id, created_by_id, auto_approve=auto_approve)
            add_parent_child_relation(spouse.id, child.id, created_by_id, auto_approve=auto_approve)
            created_children.append(child)

    if data.get("marital_status") == "married":
        for spouse_data in data.get("spouses", []):
            add_spouse_with_children(spouse_data, "current")
    elif data.get("marital_status") == "divorced" and data.get("ex_spouse"):
        add_spouse_with_children(data["ex_spouse"], "divorced")

    return main_person, created_children, created_spouses


# ---------------------------------------------------------------------------
# إضافة زوجة/زوج جديد (لم يكن مسجَّلاً من قبل) لشخص موجود مسبقاً
# ---------------------------------------------------------------------------

def add_spouse_to_person(person_id, spouse_data, created_by_id, auto_approve=False):
    """
    إضافة زوجة/زوج لشخص موجود مسبقاً، بإنشاء سجل شخص جديد له.
    يدعم تعدد الأزواج/الزوجات لكلا الجنسين دون قيد.
    """
    person = db.session.get(Person, person_id)
    if not person:
        raise ValueError("الشخص غير موجود")

    if not spouse_data.get("full_name"):
        raise ValueError("اسم الزوجة/الزوج إلزامي")

    spouse_gender = "female" if person.gender == "male" else "male"
    spouse = create_person(
        {
            "full_name": spouse_data["full_name"],
            "gender": spouse_gender,
            "tribe_name": spouse_data.get("tribe_name"),
            "tribe_branch": spouse_data.get("tribe_branch"),
            "marital_status": "married",
        },
        created_by_id, auto_approve=auto_approve,
    )

    husband_id = person.id if person.gender == "male" else spouse.id
    wife_id = spouse.id if person.gender == "male" else person.id
    create_marriage(husband_id, wife_id, created_by_id, status="current")

    created_children = []
    for child_data in spouse_data.get("children", []):
        if not child_data.get("full_name"):
            continue
        child = create_person(
            {"full_name": child_data["full_name"], "gender": child_data.get("gender", "male")},
            created_by_id, auto_approve=auto_approve,
        )
        add_parent_child_relation(person.id, child.id, created_by_id, auto_approve=auto_approve)
        add_parent_child_relation(spouse.id, child.id, created_by_id, auto_approve=auto_approve)
        created_children.append(child)

    if person.marital_status != "married":
        person.marital_status = "married"
        db.session.commit()

    return spouse, created_children


# ---------------------------------------------------------------------------
# ربط زوج/زوجة موجود مسبقاً في السجل (لا إنشاء شخص جديد)
# مثال: أخ يتزوج زوجة أخيه المتوفى — كلاهما مسجَّل بالفعل في النظام
# ---------------------------------------------------------------------------

def link_existing_spouse(person_id, spouse_id, created_by_id, marriage_status="current",
                          marriage_date=None):
    """
    يربط شخصين مسجَّلين مسبقاً بعلاقة زواج، دون إنشاء أي سجل جديد.
    يُستخدم للحالات الاستثنائية مثل زواج الأخ من زوجة أخيه المتوفى،
    حيث الطرفان معروفان في السجل أصلاً. لا يمنع تعدد الأزواج/الزوجات
    لأي من الطرفين، ولا يشترط أن يكون أحدهما "أعزب" حالياً.
    """
    person = db.session.get(Person, person_id)
    spouse = db.session.get(Person, spouse_id)
    if not person or not spouse:
        raise ValueError("أحد الشخصين غير موجود")

    if person_id == spouse_id:
        raise ValueError("لا يمكن ربط شخص بنفسه كزوج/زوجة")

    if person.gender == spouse.gender:
        raise ValueError("لا يمكن أن يكون الطرفان من نفس الجنس")

    husband_id = person.id if person.gender == "male" else spouse.id
    wife_id = spouse.id if person.gender == "male" else person.id

    duplicate = Marriage.query.filter_by(
        husband_id=husband_id, wife_id=wife_id, status=marriage_status
    ).first()
    if duplicate:
        raise ValueError("يوجد بالفعل رابط زواج بهذه الحالة بين هذين الشخصين")

    marriage = create_marriage(
        husband_id, wife_id, created_by_id,
        status=marriage_status, marriage_date=marriage_date,
    )

    return marriage, person, spouse


# ---------------------------------------------------------------------------
# إضافة والدين لشخص موجود مسبقاً
# ---------------------------------------------------------------------------

def add_parents_to_person(person_id, father_data, mother_data, created_by_id, auto_approve=False):
    person = db.session.get(Person, person_id)
    if not person:
        raise ValueError("الشخص غير موجود")

    if get_father(person_id) and father_data and father_data.get("full_name"):
        raise ValueError("لهذا الشخص أب مسجَّل بالفعل")
    if get_mother(person_id) and mother_data and mother_data.get("full_name"):
        raise ValueError("لهذا الشخص أم مسجَّلة بالفعل")

    if not (father_data and father_data.get("full_name")) and not (mother_data and mother_data.get("full_name")):
        raise ValueError("يجب إدخال اسم الأب أو الأم على الأقل")

    father = None
    mother = None

    if father_data and father_data.get("full_name"):
        father = create_person(
            {
                "full_name": father_data["full_name"],
                "gender": "male",
                "tribe_name": father_data.get("tribe_name"),
                "tribe_branch": father_data.get("tribe_branch"),
                "marital_status": "married" if mother_data and mother_data.get("full_name") else "single",
            },
            created_by_id, auto_approve=auto_approve,
        )
        add_parent_child_relation(father.id, person.id, created_by_id, auto_approve=auto_approve)

    if mother_data and mother_data.get("full_name"):
        mother = create_person(
            {
                "full_name": mother_data["full_name"],
                "gender": "female",
                "tribe_name": mother_data.get("tribe_name"),
                "tribe_branch": mother_data.get("tribe_branch"),
                "marital_status": "married" if father else "single",
            },
            created_by_id, auto_approve=auto_approve,
        )
        add_parent_child_relation(mother.id, person.id, created_by_id, auto_approve=auto_approve)

    if father and mother:
        create_marriage(father.id, mother.id, created_by_id, status="current")

    return father, mother


# ---------------------------------------------------------------------------
# إضافة / حذف ابن لزوجة موجودة مسبقاً
# ---------------------------------------------------------------------------

def add_child_to_couple(person_id, spouse_id, child_data, created_by_id, auto_approve=False):
    person = db.session.get(Person, person_id)
    spouse = db.session.get(Person, spouse_id)
    if not person or not spouse:
        raise ValueError("أحد الطرفين غير موجود")

    if not child_data.get("full_name"):
        raise ValueError("اسم الابن/الابنة إلزامي")

    marriage_exists = Marriage.query.filter(
        db.or_(
            db.and_(Marriage.husband_id == person_id, Marriage.wife_id == spouse_id),
            db.and_(Marriage.husband_id == spouse_id, Marriage.wife_id == person_id),
        )
    ).first()
    if not marriage_exists:
        raise ValueError("لا يوجد زواج مسجَّل بين هذين الشخصين")

    child = create_person(
        {"full_name": child_data["full_name"], "gender": child_data.get("gender", "male")},
        created_by_id, auto_approve=auto_approve,
    )
    add_parent_child_relation(person_id, child.id, created_by_id, auto_approve=auto_approve)
    add_parent_child_relation(spouse_id, child.id, created_by_id, auto_approve=auto_approve)

    return child


def remove_child_from_couple(person_id, spouse_id, child_id, deleted_by_id):
    remove_parent_child_relation(person_id, child_id, deleted_by_id)
    remove_parent_child_relation(spouse_id, child_id, deleted_by_id)


# ---------------------------------------------------------------------------
# دمج سجلين مكرَّرين
# ---------------------------------------------------------------------------

def merge_persons(keep_id, duplicate_id, merged_by_id):
    if keep_id == duplicate_id:
        raise ValueError("لا يمكن دمج شخص مع نفسه")

    keep = db.session.get(Person, keep_id)
    duplicate = db.session.get(Person, duplicate_id)
    if not keep or not duplicate:
        raise ValueError("أحد السجلين غير موجود")

    parent_rels = Relation.query.filter_by(parent_id=duplicate_id).all()
    for r in parent_rels:
        if r.child_id == keep_id:
            db.session.delete(r)
            continue
        exists = Relation.query.filter_by(parent_id=keep_id, child_id=r.child_id).first()
        db.session.delete(r) if exists else setattr(r, "parent_id", keep_id)

    child_rels = Relation.query.filter_by(child_id=duplicate_id).all()
    for r in child_rels:
        if r.parent_id == keep_id:
            db.session.delete(r)
            continue
        exists = Relation.query.filter_by(parent_id=r.parent_id, child_id=keep_id).first()
        db.session.delete(r) if exists else setattr(r, "child_id", keep_id)

    db.session.commit()

    marriages = Marriage.query.filter(
        db.or_(Marriage.husband_id == duplicate_id, Marriage.wife_id == duplicate_id)
    ).all()
    for m in marriages:
        if m.husband_id == duplicate_id:
            m.husband_id = keep_id
        if m.wife_id == duplicate_id:
            m.wife_id = keep_id
        if m.husband_id == m.wife_id:
            db.session.delete(m)
    db.session.commit()

    if not keep.photo_path and duplicate.photo_path:
        keep.photo_path = duplicate.photo_path
    if not keep.tribe_id and duplicate.tribe_id:
        keep.tribe_id = duplicate.tribe_id
    if not keep.birth_date and duplicate.birth_date:
        keep.birth_date = duplicate.birth_date
    if not keep.birth_place and duplicate.birth_place:
        keep.birth_place = duplicate.birth_place
    if not keep.notes and duplicate.notes:
        keep.notes = duplicate.notes
    db.session.commit()

    Closure.query.filter(
        db.or_(Closure.ancestor_id == duplicate_id, Closure.descendant_id == duplicate_id)
    ).delete()
    duplicate_public_id = duplicate.public_id
    db.session.delete(duplicate)
    db.session.commit()

    rebuild_closure_table()

    _log_audit(merged_by_id, "delete", "persons", duplicate_id,
               f"merged into keep_id={keep_id} (public_id={duplicate_public_id})")

    return keep


# ---------------------------------------------------------------------------
# البحث والعرض
# ---------------------------------------------------------------------------

def get_parental_info(person_id):
    mother = get_mother(person_id)
    father = get_father(person_id)

    return {
        "father_name": father.full_name if father else None,
        "mother_name": mother.full_name if mother else None,
        "maternal_tribe": mother.tribe.tribe_name if (mother and mother.tribe) else None,
    }


def search_persons(query_text, only_approved=True):
    q = Person.query.filter(Person.full_name.ilike(f"%{query_text.strip()}%"))
    if only_approved:
        q = q.filter(Person.status == "approved")

    results = q.order_by(Person.full_name.asc()).all()

    enriched = []
    for p in results:
        parental = get_parental_info(p.id)
        enriched.append({"person": p, **parental})
    return enriched


def search_persons_by_gender(query_text, required_gender, exclude_id=None, only_approved=True):
    """
    بحث مقيَّد بجنس محدد — يُستخدم عند اختيار زوج/زوجة موجود مسبقاً،
    حتى لا تظهر أسماء من نفس جنس الشخص الأساسي في نتائج الاختيار.
    """
    q = Person.query.filter(
        Person.full_name.ilike(f"%{query_text.strip()}%"),
        Person.gender == required_gender,
    )
    if exclude_id:
        q = q.filter(Person.id != exclude_id)
    if only_approved:
        q = q.filter(Person.status == "approved")

    return q.order_by(Person.full_name.asc()).limit(8).all()


def get_visible_person_data(person, viewer_role):
    data = {
        "id": person.id,
        "public_id": person.public_id,
        "full_name": person.full_name,
        "gender": person.gender,
        "tribe": person.tribe.tribe_name if person.tribe else None,
        "marital_status": person.marital_status,
        "notes": person.notes,
    }

    if person.is_living and viewer_role not in ("admin",):
        data["photo_path"] = None
        data["birth_date"] = None
    else:
        data["photo_path"] = person.photo_path
        data["birth_date"] = person.birth_date

    return data
