from app.extensions import db
from app.models import Tribe, Person
from app.services.relation_service import _log_audit


# ---------------------------------------------------------------------------
# قراءة
# ---------------------------------------------------------------------------

def list_tribes_with_counts():
    """
    يعيد كل العشائر/الفروع مرتبة أبجدياً، مع عدد الأفراد المرتبطين بكل واحدة
    (يُستخدم لعرض القائمة ولمنع حذف عشيرة لا تزال مستخدمة).
    """
    tribes = Tribe.query.order_by(Tribe.tribe_name.asc(), Tribe.branch_name.asc()).all()

    result = []
    for t in tribes:
        count = Person.query.filter_by(tribe_id=t.id).count()
        result.append({"tribe": t, "person_count": count})
    return result


def get_tribe(tribe_id):
    return db.session.get(Tribe, tribe_id)


# ---------------------------------------------------------------------------
# إنشاء / تعديل / حذف
# ---------------------------------------------------------------------------

def create_tribe(tribe_name, branch_name, created_by_id):
    tribe_name = (tribe_name or "").strip()
    if not tribe_name:
        raise ValueError("اسم العشيرة إلزامي")

    branch_name = (branch_name or "").strip() or None

    duplicate = Tribe.query.filter_by(tribe_name=tribe_name, branch_name=branch_name).first()
    if duplicate:
        raise ValueError("هذه العشيرة/الفرع مسجّل بالفعل")

    tribe = Tribe(tribe_name=tribe_name, branch_name=branch_name)
    db.session.add(tribe)
    db.session.commit()

    _log_audit(created_by_id, "create", "tribes", tribe.id,
               f"tribe_name={tribe_name} branch_name={branch_name}")
    return tribe


def update_tribe(tribe_id, tribe_name, branch_name, updated_by_id):
    tribe = db.session.get(Tribe, tribe_id)
    if not tribe:
        raise ValueError("العشيرة غير موجودة")

    tribe_name = (tribe_name or "").strip()
    if not tribe_name:
        raise ValueError("اسم العشيرة إلزامي")

    branch_name = (branch_name or "").strip() or None

    duplicate = Tribe.query.filter(
        Tribe.id != tribe_id,
        Tribe.tribe_name == tribe_name,
        Tribe.branch_name == branch_name,
    ).first()
    if duplicate:
        raise ValueError("توجد عشيرة/فرع بنفس الاسم بالفعل")

    old = f"tribe_name={tribe.tribe_name} branch_name={tribe.branch_name}"
    tribe.tribe_name = tribe_name
    tribe.branch_name = branch_name
    db.session.commit()

    _log_audit(updated_by_id, "update", "tribes", tribe.id,
               f"{old} -> tribe_name={tribe_name} branch_name={branch_name}")
    return tribe


def delete_tribe(tribe_id, deleted_by_id):
    """
    يحذف عشيرة/فرع فقط إذا لم يكن أي شخص مرتبطاً بها حالياً، لتفادي ترك
    أفراد بمرجع تالف (tribe_id يشير إلى صف محذوف).
    """
    tribe = db.session.get(Tribe, tribe_id)
    if not tribe:
        raise ValueError("العشيرة غير موجودة")

    linked_count = Person.query.filter_by(tribe_id=tribe_id).count()
    if linked_count > 0:
        raise ValueError(
            f"لا يمكن حذف هذه العشيرة — يوجد {linked_count} فرد/أفراد مرتبطين بها حالياً"
        )

    details = f"tribe_name={tribe.tribe_name} branch_name={tribe.branch_name}"
    db.session.delete(tribe)
    db.session.commit()

    _log_audit(deleted_by_id, "delete", "tribes", tribe_id, details)
