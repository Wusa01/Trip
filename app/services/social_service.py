from app.extensions import db
from app.models import Person, SocialLink
from app.services.person_service import create_person_full
from app.services.relation_service import _log_audit


VALID_ENTRY_TYPES = ("friend", "neighbor")


# ---------------------------------------------------------------------------
# إنشاء صديق/جار جديد — بنفس آلية إنشاء فرد كامل (زوجة/زوجات + أبناء)
# مع تمييز الجميع كـ person_type = friend/neighbor، وربط اختياري بفرد
# من العشيرة (مثلاً: "هذا صديق لفلان بن فلان").
# ---------------------------------------------------------------------------

def create_social_entry(data, entry_type, created_by_id, linked_person_id=None,
                         link_note=None, auto_approve=False):
    if entry_type not in VALID_ENTRY_TYPES:
        raise ValueError("نوع الإدخال يجب أن يكون صديق أو جار")

    if linked_person_id:
        linked = db.session.get(Person, linked_person_id)
        if not linked:
            raise ValueError("الشخص المرتبط من العشيرة غير موجود")

    payload = dict(data)
    payload["person_type"] = entry_type

    main_person, children, spouses = create_person_full(payload, created_by_id, auto_approve=auto_approve)

    # الزوجة/الزوجات والأبناء يُنشؤون داخلياً بدون person_type، لذا نصحّحه
    # هنا كي تبقى العائلة كاملة مصنّفة خارج نسب العشيرة الأصلي.
    changed = False
    for p in spouses + children:
        if p.person_type != entry_type:
            p.person_type = entry_type
            changed = True
    if changed:
        db.session.commit()

    if linked_person_id:
        link = SocialLink(
            person_id=main_person.id,
            linked_person_id=linked_person_id,
            note=(link_note or "").strip() or None,
            created_by=created_by_id,
        )
        db.session.add(link)
        db.session.commit()
        _log_audit(created_by_id, "create", "social_links", link.id,
                   f"person_id={main_person.id} linked_person_id={linked_person_id}")

    return main_person, children, spouses


# ---------------------------------------------------------------------------
# عرض القائمة
# ---------------------------------------------------------------------------

def list_social_entries(entry_type=None, only_approved=True):
    q = Person.query.filter(Person.person_type.in_(VALID_ENTRY_TYPES))
    if entry_type in VALID_ENTRY_TYPES:
        q = q.filter(Person.person_type == entry_type)
    if only_approved:
        q = q.filter(Person.status == "approved")

    persons = q.order_by(Person.full_name.asc()).all()
    if not persons:
        return []

    links = {
        link.person_id: link
        for link in SocialLink.query.filter(SocialLink.person_id.in_([p.id for p in persons])).all()
    }

    results = []
    for person in persons:
        link = links.get(person.id)
        results.append({
            "person": person,
            "linked_person": link.linked_person if link else None,
            "link_note": link.note if link else None,
        })
    return results


def update_social_link(person_id, linked_person_id, note, updated_by_id):
    """يحدّث أو يضيف أو يحذف رابط شخص العشيرة لصديق/جار موجود مسبقاً."""
    person = db.session.get(Person, person_id)
    if not person or person.person_type not in VALID_ENTRY_TYPES:
        raise ValueError("هذا الشخص ليس صديقاً أو جاراً")

    link = SocialLink.query.filter_by(person_id=person_id).first()

    if not linked_person_id:
        if link:
            db.session.delete(link)
            db.session.commit()
        return None

    linked = db.session.get(Person, linked_person_id)
    if not linked:
        raise ValueError("الشخص المرتبط من العشيرة غير موجود")

    if not link:
        link = SocialLink(person_id=person_id, created_by=updated_by_id)
        db.session.add(link)

    link.linked_person_id = linked_person_id
    link.note = (note or "").strip() or None
    db.session.commit()
    return link
