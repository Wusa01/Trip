from app.models import Person, Tribe, Relation


def get_dashboard_stats(viewer_role):
    """
    إحصائيات الصفحة الرئيسية. عدد الإضافات المعلَّقة يظهر للمدير فقط
    (هو من يملك صلاحية اعتمادها أصلاً).
    """
    # الإحصائيات تخص نسب العشيرة الأصلي فقط — الأصدقاء والجيران (person_type
    # friend/neighbor) لهم صفحتهم الخاصة ولا يُحتسبون هنا حتى لا يشوّهوا
    # أعداد أفراد العشيرة.
    total_persons = Person.query.filter_by(status="approved", person_type="family").count()
    males_count = Person.query.filter_by(status="approved", person_type="family", gender="male").count()
    females_count = Person.query.filter_by(status="approved", person_type="family", gender="female").count()
    total_tribes = Tribe.query.count()

    stats = {
        "total_persons": total_persons,
        "males_count": males_count,
        "females_count": females_count,
        "total_tribes": total_tribes,
        "pending_count": None,
    }

    if viewer_role == "admin":
        pending_persons = Person.query.filter_by(status="pending").count()
        pending_relations = Relation.query.filter_by(status="pending").count()
        stats["pending_count"] = pending_persons + pending_relations

    stats["recent_persons"] = (
        Person.query.filter_by(status="approved", person_type="family")
        .order_by(Person.created_at.desc())
        .limit(6)
        .all()
    )

    return stats
