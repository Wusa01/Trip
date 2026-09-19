from datetime import datetime
from flask_login import UserMixin
from app.extensions import db


class Tribe(db.Model):
    """العشيرة والفرع العائلي (تُستخدم لعشيرة الشخص وعشيرة الزوج/الزوجة)"""
    __tablename__ = "tribes"

    id = db.Column(db.Integer, primary_key=True)
    tribe_name = db.Column(db.String(150), nullable=False)
    branch_name = db.Column(db.String(150), nullable=True)

    persons = db.relationship("Person", back_populates="tribe")

    def __repr__(self):
        return f"<Tribe {self.tribe_name} - {self.branch_name}>"


class User(UserMixin, db.Model):
    """مستخدمو النظام: admin | user | researcher | inactive"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_active(self):
        """
        يُستخدم من flask_login عند تسجيل الدخول: المستخدم المعطَّل
        (role == 'inactive') يُمنع من الدخول فعلياً، لا فقط شكلياً في الواجهة.
        """
        return self.role != "inactive"

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Person(db.Model):
    """بطاقة الفرد الأساسية"""
    __tablename__ = "persons"

    id = db.Column(db.Integer, primary_key=True)

    # معرف عام فريد يُطبع على البطاقة، يحل مشكلة تكرار الأسماء المتشابهة
    public_id = db.Column(db.String(20), unique=True, nullable=False, index=True)

    full_name = db.Column(db.String(200), nullable=False, index=True)
    gender = db.Column(db.String(10), nullable=False)  # male | female

    photo_path = db.Column(db.String(255), nullable=True)

    tribe_id = db.Column(db.Integer, db.ForeignKey("tribes.id"), nullable=True)
    tribe = db.relationship("Tribe", back_populates="persons")

    birth_date = db.Column(db.Date, nullable=True)
    birth_place = db.Column(db.String(150), nullable=True)
    death_date = db.Column(db.Date, nullable=True)

    # single | married | divorced | widowed
    marital_status = db.Column(db.String(20), nullable=False, default="single")

    # حقل تمييز إضافي (كنية، ترتيب بين الإخوة...) لحل تكرار الأسماء المتطابقة
    disambiguation_note = db.Column(db.String(255), nullable=True)

    notes = db.Column(db.Text, nullable=True)

    # يتحكم في إخفاء الصورة/تاريخ الميلاد عن غير المدير حماية لخصوصية الأحياء
    is_living = db.Column(db.Boolean, nullable=False, default=True)

    # pending | approved | rejected — لدعم مراجعة إضافات الباحث
    status = db.Column(db.String(20), nullable=False, default="pending")

    # family (فرد من نسب العشيرة نفسها) | friend (صديق) | neighbor (جار)
    # يُستخدم لفصل شبكة العلاقات الاجتماعية (الأصدقاء/الجيران وعائلاتهم)
    # عن نسب العشيرة الأصلي، مع بقاء نفس آلية الشجرة/الزواج/الأبناء.
    person_type = db.Column(db.String(20), nullable=False, default="family")

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Person {self.public_id} {self.full_name}>"


class Relation(db.Model):
    """
    نخزن اتجاهاً واحداً فقط: PARENT_OF (من الأب/الأم إلى الابن/الابنة).
    العلاقات العكسية (ابن/بنت) وعلاقة الإخوة تُشتق في relation_service
    ولا تُخزن مباشرة، لتفادي التناقضات عند إدخال العلاقة مرتين بشكل معاكس.
    الأب أو الأم يُحدَّد تلقائياً من جنس parent، فلا حاجة لحقل منفصل.
    """
    __tablename__ = "relations"

    id = db.Column(db.Integer, primary_key=True)

    parent_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False)

    relation_type = db.Column(db.String(20), nullable=False, default="PARENT_OF")
    status = db.Column(db.String(20), nullable=False, default="pending")

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parent = db.relationship("Person", foreign_keys=[parent_id])
    child = db.relationship("Person", foreign_keys=[child_id])

    __table_args__ = (
        db.UniqueConstraint("parent_id", "child_id", name="uq_parent_child"),
    )


class Closure(db.Model):
    """
    جدول إغلاق الأنساب (Closure Table): يسرّع استعلامات
    'من الشخص إلى الجد الأعلى' أو 'كل أحفاد شخص' دون recursive query في كل مرة.
    كل صف: ancestor سلف لـ descendant بفارق depth من الأجيال.
    كل شخص مُدرج كسلف/سليل لنفسه بـ depth = 0.
    يُحدَّث تلقائياً في relation_service عند اعتماد كل علاقة PARENT_OF جديدة.
    """
    __tablename__ = "closure"

    ancestor_id = db.Column(db.Integer, db.ForeignKey("persons.id"), primary_key=True)
    descendant_id = db.Column(db.Integer, db.ForeignKey("persons.id"), primary_key=True)
    depth = db.Column(db.Integer, nullable=False)


class Marriage(db.Model):
    """يدعم تعدد الزوجات، الطلاق، والترمّل دون حذف السجل السابق"""
    __tablename__ = "marriages"

    id = db.Column(db.Integer, primary_key=True)

    husband_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False)
    wife_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False)

    # current | divorced | widowed
    status = db.Column(db.String(20), nullable=False, default="current")

    marriage_date = db.Column(db.Date, nullable=True)
    divorce_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    husband = db.relationship("Person", foreign_keys=[husband_id])
    wife = db.relationship("Person", foreign_keys=[wife_id])


class SocialLink(db.Model):
    """
    ربط اختياري بين جذر شخص خارجي (صديق/جار) وأحد أفراد العشيرة الذي
    تربطه به هذه العلاقة (مثلاً: "هذا صديق لفلان بن فلان"). الربط اختياري —
    يمكن تسجيل صديق/جار دون تحديد فرد معيّن من العشيرة.
    """
    __tablename__ = "social_links"

    id = db.Column(db.Integer, primary_key=True)

    # جذر عائلة الصديق/الجار (person.person_type == friend|neighbor)
    person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False)

    # الفرد من العشيرة المرتبط به، إن وُجد
    linked_person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=True)

    note = db.Column(db.String(255), nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    person = db.relationship("Person", foreign_keys=[person_id])
    linked_person = db.relationship("Person", foreign_keys=[linked_person_id])

    def __repr__(self):
        return f"<SocialLink person={self.person_id} linked={self.linked_person_id}>"


class AuditLog(db.Model):
    """سجل تدقيق: من أضاف/عدّل/اعتمد أي سجل ومتى — مهم لحل النزاعات العائلية"""
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    action = db.Column(db.String(20), nullable=False)   # create | update | delete | approve | reject
    table_name = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    details = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
