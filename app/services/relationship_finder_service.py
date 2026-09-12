from app.extensions import db
from app.models import Person, Closure
from app.services.relation_service import get_ancestors, get_parents


# أوصاف جاهزة لأكثر أنماط القرابة شيوعاً، حسب (بعد الشخص الأول عن السلف المشترك، بعد الشخص الثاني عنه)
_RELATION_LABELS = {
    (0, 0): "الشخص نفسه",
    (1, 0): "علاقة أب/أم مباشرة",
    (0, 1): "علاقة أب/أم مباشرة",
    (1, 1): "إخوة (من نفس الأب أو الأم)",
    (2, 0): "جد/جدة مباشر",
    (0, 2): "جد/جدة مباشر",
    (2, 1): "عم/عمة أو خال/خالة",
    (1, 2): "عم/عمة أو خال/خالة",
    (2, 2): "أبناء عمومة/خؤولة من الدرجة الأولى",
    (3, 1): "عم/عمة أو خال/خالة الأب أو الأم (بعيد)",
    (1, 3): "عم/عمة أو خال/خالة الأب أو الأم (بعيد)",
    (3, 2): "أبناء عمومة/خؤولة من الدرجة الثانية",
    (2, 3): "أبناء عمومة/خؤولة من الدرجة الثانية",
}


def _describe_relation(depth_a, depth_b):
    key = (depth_a, depth_b)
    if key in _RELATION_LABELS:
        return _RELATION_LABELS[key]
    return f"قرابة بعيدة (يبعد كل منهما {max(depth_a, depth_b)} أجيال تقريباً عن السلف المشترك)"


def _build_chain_to_ancestor(start_id, ancestor_id):
    """يبني سلسلة الأشخاص الفعلية من start_id صعوداً حتى ancestor_id، باستخدام Closure كدليل اتجاه"""
    chain = [start_id]
    current = start_id

    if current == ancestor_id:
        return chain

    safety = 0
    while current != ancestor_id and safety < 50:
        safety += 1
        parents = get_parents(current)
        next_parent = None
        for p in parents:
            if p.id == ancestor_id:
                next_parent = p
                break
            is_on_path = Closure.query.filter_by(ancestor_id=ancestor_id, descendant_id=p.id).first()
            if is_on_path:
                next_parent = p
                break
        if not next_parent:
            break
        chain.append(next_parent.id)
        current = next_parent.id

    return chain


def find_relationship(person_a_id, person_b_id):
    """
    يبحث عن أقرب سلف مشترك بين شخصين عبر جدول الإغلاق، ويبني المسار الكامل
    بينهما (من الشخص الأول صعوداً للسلف المشترك، ثم نزولاً للشخص الثاني).
    """
    person_a = db.session.get(Person, person_a_id)
    person_b = db.session.get(Person, person_b_id)
    if not person_a or not person_b:
        raise ValueError("أحد الشخصين غير موجود")

    if person_a_id == person_b_id:
        raise ValueError("الرجاء اختيار شخصين مختلفين")

    ancestors_a = {person_a_id: 0}
    for a, depth in get_ancestors(person_a_id):
        ancestors_a[a.id] = depth

    ancestors_b = {person_b_id: 0}
    for b, depth in get_ancestors(person_b_id):
        ancestors_b[b.id] = depth

    common_ids = set(ancestors_a.keys()) & set(ancestors_b.keys())
    if not common_ids:
        raise ValueError("لا توجد قرابة معروفة بين هذين الشخصين في السجل الحالي")

    best_id = min(common_ids, key=lambda cid: ancestors_a[cid] + ancestors_b[cid])
    depth_a = ancestors_a[best_id]
    depth_b = ancestors_b[best_id]

    common_ancestor = db.session.get(Person, best_id)

    chain_a = _build_chain_to_ancestor(person_a_id, best_id)
    chain_b = _build_chain_to_ancestor(person_b_id, best_id)

    full_path_ids = chain_a + list(reversed(chain_b[:-1]))

    def to_dict(pid):
        p = db.session.get(Person, pid)
        return {
            "id": p.id,
            "public_id": p.public_id,
            "full_name": p.full_name,
            "gender": p.gender,
            "tribe": p.tribe.tribe_name if p.tribe else None,
        }

    return {
        "person_a": to_dict(person_a_id),
        "person_b": to_dict(person_b_id),
        "common_ancestor": to_dict(best_id),
        "depth_a": depth_a,
        "depth_b": depth_b,
        "relation_label": _describe_relation(depth_a, depth_b),
        "path": [to_dict(pid) for pid in full_path_ids],
    }
