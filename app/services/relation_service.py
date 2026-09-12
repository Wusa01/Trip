from datetime import datetime
from app.extensions import db
from app.models import Relation, Closure, Person, AuditLog, Marriage


# ---------------------------------------------------------------------------
# جدول الإغلاق (Closure Table)
# ---------------------------------------------------------------------------

def ensure_self_closure(person_id):
    exists = Closure.query.filter_by(
        ancestor_id=person_id, descendant_id=person_id
    ).first()
    if not exists:
        db.session.add(Closure(ancestor_id=person_id, descendant_id=person_id, depth=0))
        db.session.commit()


def _add_closure_edge(parent_id, child_id):
    ensure_self_closure(parent_id)
    ensure_self_closure(child_id)

    ancestors_of_parent = Closure.query.filter_by(descendant_id=parent_id).all()
    descendants_of_child = Closure.query.filter_by(ancestor_id=child_id).all()

    new_rows = []
    for a in ancestors_of_parent:
        for d in descendants_of_child:
            depth = a.depth + 1 + d.depth
            already = Closure.query.filter_by(
                ancestor_id=a.ancestor_id, descendant_id=d.descendant_id
            ).first()
            if not already:
                new_rows.append(
                    Closure(ancestor_id=a.ancestor_id, descendant_id=d.descendant_id, depth=depth)
                )

    db.session.bulk_save_objects(new_rows)
    db.session.commit()


def would_create_cycle(parent_id, child_id):
    existing = Closure.query.filter_by(
        ancestor_id=child_id, descendant_id=parent_id
    ).first()
    return existing is not None


def rebuild_closure_table():
    """
    يُعيد بناء جدول الإغلاق بالكامل من الصفر اعتماداً على العلاقات المعتمدة فقط.
    يُستدعى بعد حذف أو تصحيح أي علاقة.
    """
    Closure.query.delete()
    db.session.commit()

    for p in Person.query.all():
        db.session.add(Closure(ancestor_id=p.id, descendant_id=p.id, depth=0))
    db.session.commit()

    relations = Relation.query.filter_by(status="approved").all()

    changed = True
    max_passes = len(relations) + 2
    passes = 0
    while changed and passes < max_passes:
        changed = False
        passes += 1
        for r in relations:
            before = Closure.query.filter_by(
                ancestor_id=r.parent_id, descendant_id=r.child_id
            ).first()
            _add_closure_edge(r.parent_id, r.child_id)
            after_count = Closure.query.filter_by(
                ancestor_id=r.parent_id, descendant_id=r.child_id
            ).count()
            if not before and after_count:
                changed = True


# ---------------------------------------------------------------------------
# إدارة علاقات الأبوة (إضافة / اعتماد / رفض / حذف)
# ---------------------------------------------------------------------------

def add_parent_child_relation(parent_id, child_id, created_by_id, auto_approve=False):
    if parent_id == child_id:
        raise ValueError("لا يمكن أن يكون الشخص أباً/أماً لنفسه")

    if would_create_cycle(parent_id, child_id):
        raise ValueError("هذه العلاقة تُنشئ تسلسلاً دائرياً في النسب")

    duplicate = Relation.query.filter_by(parent_id=parent_id, child_id=child_id).first()
    if duplicate:
        raise ValueError("هذه العلاقة موجودة بالفعل")

    relation = Relation(
        parent_id=parent_id,
        child_id=child_id,
        relation_type="PARENT_OF",
        status="approved" if auto_approve else "pending",
        created_by=created_by_id,
    )
    db.session.add(relation)
    db.session.commit()

    _log_audit(created_by_id, "create", "relations", relation.id,
               f"parent={parent_id} child={child_id} status={relation.status}")

    if auto_approve:
        _add_closure_edge(parent_id, child_id)

    return relation


def approve_relation(relation_id, approver_id):
    relation = db.session.get(Relation, relation_id)
    if not relation:
        raise ValueError("العلاقة غير موجودة")
    if relation.status == "approved":
        return relation

    relation.status = "approved"
    db.session.commit()

    _add_closure_edge(relation.parent_id, relation.child_id)
    _log_audit(approver_id, "approve", "relations", relation.id, "")
    return relation


def reject_relation(relation_id, approver_id, reason=""):
    relation = db.session.get(Relation, relation_id)
    if not relation:
        raise ValueError("العلاقة غير موجودة")

    relation.status = "rejected"
    db.session.commit()
    _log_audit(approver_id, "reject", "relations", relation.id, reason)
    return relation


def delete_relation(relation_id, deleted_by_id):
    """
    يحذف رابط أبوة خاطئاً بالكامل، ويعيد بناء جدول الإغلاق فوراً.
    لا يحذف الشخصين أنفسهما، فقط الرابط بينهما.
    """
    relation = db.session.get(Relation, relation_id)
    if not relation:
        raise ValueError("العلاقة غير موجودة")

    details = f"parent={relation.parent_id} child={relation.child_id}"
    db.session.delete(relation)
    db.session.commit()

    rebuild_closure_table()

    _log_audit(deleted_by_id, "delete", "relations", relation_id, details)


def remove_parent_child_relation(parent_id, child_id, deleted_by_id):
    """
    يحذف رابط أبوة محدد بين شخصين معروفين (وليس عبر relation_id مباشرة) —
    يُستخدم لتصحيح ابن أُضيف بالخطأ تحت زوجة معينة.
    """
    relation = Relation.query.filter_by(parent_id=parent_id, child_id=child_id).first()
    if not relation:
        raise ValueError("لا توجد علاقة بين هذين الشخصين")

    delete_relation(relation.id, deleted_by_id)


# ---------------------------------------------------------------------------
# استعلامات العلاقات الأساسية
# ---------------------------------------------------------------------------

def get_parents(person_id):
    rows = Relation.query.filter_by(child_id=person_id, status="approved").all()
    return [r.parent for r in rows]


def get_parent_relations(person_id):
    return Relation.query.filter_by(child_id=person_id, status="approved").all()


def get_children(person_id):
    rows = Relation.query.filter_by(parent_id=person_id, status="approved").all()
    return [r.child for r in rows]


def get_mother(person_id):
    for parent in get_parents(person_id):
        if parent.gender == "female":
            return parent
    return None


def get_father(person_id):
    for parent in get_parents(person_id):
        if parent.gender == "male":
            return parent
    return None


def get_siblings(person_id):
    parent_ids = [p.id for p in get_parents(person_id)]
    if not parent_ids:
        return []

    sibling_ids = set()
    for pid in parent_ids:
        for child in get_children(pid):
            if child.id != person_id:
                sibling_ids.add(child.id)

    return Person.query.filter(Person.id.in_(sibling_ids)).all()


def get_ancestors(person_id, max_depth=None):
    query = Closure.query.filter(
        Closure.descendant_id == person_id, Closure.depth > 0
    ).order_by(Closure.depth.asc())
    if max_depth:
        query = query.filter(Closure.depth <= max_depth)

    rows = query.all()
    return [(db.session.get(Person, r.ancestor_id), r.depth) for r in rows]


def get_descendants(person_id, max_depth=None):
    query = Closure.query.filter(
        Closure.ancestor_id == person_id, Closure.depth > 0
    ).order_by(Closure.depth.asc())
    if max_depth:
        query = query.filter(Closure.depth <= max_depth)

    rows = query.all()
    return [(db.session.get(Person, r.descendant_id), r.depth) for r in rows]


def get_relation_label(person):
    return "أم" if person.gender == "female" else "أب"


def get_child_label(person):
    return "ابنة" if person.gender == "female" else "ابن"


# ---------------------------------------------------------------------------
# الزواج والزوجات مع أبناء كل زوجة تحديداً
# ---------------------------------------------------------------------------

def create_marriage(husband_id, wife_id, created_by_id, status="current",
                     marriage_date=None, divorce_date=None):
    marriage = Marriage(
        husband_id=husband_id,
        wife_id=wife_id,
        status=status,
        marriage_date=marriage_date,
        divorce_date=divorce_date,
        created_by=created_by_id,
    )
    db.session.add(marriage)
    db.session.commit()

    husband = db.session.get(Person, husband_id)
    wife = db.session.get(Person, wife_id)
    husband.marital_status = "married" if status == "current" else "divorced"
    wife.marital_status = "married" if status == "current" else "divorced"
    db.session.commit()

    _log_audit(created_by_id, "create", "marriages", marriage.id,
               f"husband={husband_id} wife={wife_id} status={status}")
    return marriage


def get_spouses_with_children(person_id):
    marriages = Marriage.query.filter(
        db.or_(Marriage.husband_id == person_id, Marriage.wife_id == person_id)
    ).all()

    own_children_ids = {c.id for c in get_children(person_id)}

    result = []
    for m in marriages:
        spouse_id = m.wife_id if m.husband_id == person_id else m.husband_id
        spouse = db.session.get(Person, spouse_id)
        spouse_children_ids = {c.id for c in get_children(spouse_id)}

        shared_ids = own_children_ids & spouse_children_ids
        shared_children = Person.query.filter(Person.id.in_(shared_ids)).all() if shared_ids else []

        result.append({
            "spouse": spouse,
            "marriage_status": m.status,
            "children": shared_children,
        })

    return result


# ---------------------------------------------------------------------------
# سجل التدقيق
# ---------------------------------------------------------------------------

def _log_audit(user_id, action, table_name, record_id, details):
    log = AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        details=details,
        created_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
