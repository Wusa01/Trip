from app.extensions import db
from app.models import Person
from app.services.relation_service import (
    get_ancestors, get_descendants, get_children, get_parents, get_spouses_with_children,
)


def get_local_subtree(person_id, up_levels=2, down_levels=2):
    """
    يبني الفرع المحلي حول شخص (وليس الشجرة كاملة) للعرض التفاعلي.
    يشمل الآن: علاقات الأبوة (خط متصل) + روابط الزواج (خط منقّط)
    للأزواج المباشرين لكل شخص ظاهر في الفرع، مع بيانات الجنس والعشيرة
    لكل عقدة لتلوينها وتمييزها في الواجهة.
    """
    center = db.session.get(Person, person_id)
    if not center:
        raise ValueError("الشخص غير موجود")

    nodes = {}
    edges = []
    edge_keys = set()

    def add_node(person):
        if person.id not in nodes:
            nodes[person.id] = {
                "id": person.id,
                "public_id": person.public_id,
                "full_name": person.full_name,
                "gender": person.gender,
                "tribe": person.tribe.tribe_name if person.tribe else None,
                "status": person.status,
                "is_center": person.id == person_id,
            }

    def add_parent_edge(parent_id, child_id):
        key = ("parent", parent_id, child_id)
        if key not in edge_keys:
            edge_keys.add(key)
            edges.append({"source": parent_id, "target": child_id, "type": "parent"})

    def add_marriage_edge(a_id, b_id):
        key = ("marriage", min(a_id, b_id), max(a_id, b_id))
        if key not in edge_keys:
            edge_keys.add(key)
            edges.append({"source": a_id, "target": b_id, "type": "marriage"})

    add_node(center)

    def link_parents(pid, remaining):
        if remaining <= 0:
            return
        for parent in get_parents(pid):
            add_node(parent)
            add_parent_edge(parent.id, pid)
            link_parents(parent.id, remaining - 1)

    def link_children(pid, remaining):
        if remaining <= 0:
            return
        for child in get_children(pid):
            add_node(child)
            add_parent_edge(pid, child.id)
            link_children(child.id, remaining - 1)

    link_parents(person_id, up_levels)
    link_children(person_id, down_levels)

    # روابط الزواج المباشرة لكل شخص ظاهر حالياً في الفرع — تُضاف الزوجة/الزوج
    # كعقدة حتى لو لم تكن ضمن نطاق up/down، لأن الزواج جزء أساسي من الصورة الكاملة
    for existing_id in list(nodes.keys()):
        for item in get_spouses_with_children(existing_id):
            spouse = item["spouse"]
            add_node(spouse)
            add_marriage_edge(existing_id, spouse.id)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "center_id": person_id,
    }


def get_lineage_report(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        raise ValueError("الشخص غير موجود")

    ancestors = get_ancestors(person_id)
    chain = [{"full_name": person.full_name, "public_id": person.public_id, "depth": 0}]
    chain += [
        {"full_name": a.full_name, "public_id": a.public_id, "depth": depth}
        for a, depth in ancestors
    ]
    return chain


def get_branch_report(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        raise ValueError("الشخص غير موجود")

    descendants = get_descendants(person_id)

    males = sum(1 for d, _ in descendants if d.gender == "male")
    females = sum(1 for d, _ in descendants if d.gender == "female")

    children = [d for d, depth in descendants if depth == 1]
    grandchildren = [d for d, depth in descendants if depth == 2]

    return {
        "root": {"full_name": person.full_name, "public_id": person.public_id},
        "males_count": males,
        "females_count": females,
        "total_count": len(descendants),
        "children": [{"full_name": c.full_name, "public_id": c.public_id} for c in children],
        "grandchildren": [{"full_name": g.full_name, "public_id": g.public_id} for g in grandchildren],
    }
