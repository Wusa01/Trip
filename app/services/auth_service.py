import re
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User
from app.services.relation_service import _log_audit
from app.services.email_service import send_verification_code, EmailSendError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_VALID_MINUTES = 15


def _validate_email(email):
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("صيغة البريد الإلكتروني غير صحيحة")
    return email


def _validate_new_password(password, confirm_password):
    if not password or len(password) < 6:
        raise ValueError("كلمة المرور يجب أن تكون 6 أحرف على الأقل")
    if password != confirm_password:
        raise ValueError("كلمتا المرور غير متطابقتين")


# ---------------------------------------------------------------------------
# إنشاء أول حساب مدير (بتحقق من ملكية البريد عبر رمز)
# ---------------------------------------------------------------------------

def no_users_exist():
    return User.query.first() is None


def start_first_admin_signup(username, email, password, confirm_password):
    """
    يُتحقق من صحة المدخلات، يولّد رمز تفعيل من 6 أرقام ويرسله بالبريد،
    ويعيد بيانات مؤقتة (تُخزَّن في session) لإتمام إنشاء الحساب لاحقاً
    بعد تأكيد الرمز — لا يُنشأ أي حساب في قاعدة البيانات بعد.
    """
    if not no_users_exist():
        raise ValueError("يوجد حساب مسجَّل بالفعل في النظام")

    username = (username or "").strip()
    if not username:
        raise ValueError("اسم المستخدم إلزامي")

    email = _validate_email(email)
    _validate_new_password(password, confirm_password)

    code = f"{secrets.randbelow(1000000):06d}"

    try:
        send_verification_code(email, code)
    except EmailSendError as e:
        raise ValueError(str(e))

    return {
        "username": username,
        "email": email,
        "password_hash": generate_password_hash(password),
        "code": code,
        "generated_at": datetime.utcnow().isoformat(),
    }


def complete_first_admin_signup(pending, entered_code):
    """
    يتحقق من الرمز المُدخَل مقابل بيانات pending المخزَّنة في session،
    وينشئ حساب المدير الأول عند التطابق.
    """
    if not pending:
        raise ValueError("انتهت صلاحية عملية التسجيل، ابدأ من جديد")

    generated_at = datetime.fromisoformat(pending["generated_at"])
    if datetime.utcnow() - generated_at > timedelta(minutes=CODE_VALID_MINUTES):
        raise ValueError("انتهت صلاحية رمز التفعيل، اطلب رمزاً جديداً")

    if (entered_code or "").strip() != pending["code"]:
        raise ValueError("رمز التفعيل غير صحيح")

    if not no_users_exist():
        raise ValueError("يوجد حساب مسجَّل بالفعل في النظام")

    if User.query.filter_by(username=pending["username"]).first():
        raise ValueError("اسم المستخدم أصبح مستخدَماً، ابدأ من جديد باسم آخر")

    user = User(
        username=pending["username"],
        email=pending["email"],
        password_hash=pending["password_hash"],
        role="admin",
    )
    db.session.add(user)
    db.session.commit()

    _log_audit(user.id, "create", "users", user.id, f"first admin signup username={user.username}")
    return user


# ---------------------------------------------------------------------------
# تعديل الحساب الشخصي (لأي مستخدم مسجَّل دخوله)
# ---------------------------------------------------------------------------

def update_own_profile(user, new_username, new_email, current_password, new_password="", confirm_new_password=""):
    if not check_password_hash(user.password_hash, current_password or ""):
        raise ValueError("كلمة المرور الحالية غير صحيحة")

    new_username = (new_username or "").strip()
    if not new_username:
        raise ValueError("اسم المستخدم إلزامي")

    if new_username != user.username and User.query.filter_by(username=new_username).first():
        raise ValueError("اسم المستخدم مستخدَم بالفعل")

    new_email = _validate_email(new_email) if new_email else None

    changes = []
    if new_username != user.username:
        changes.append(f"username: {user.username} -> {new_username}")
        user.username = new_username
    if new_email != user.email:
        changes.append(f"email: {user.email} -> {new_email}")
        user.email = new_email

    if new_password:
        _validate_new_password(new_password, confirm_new_password)
        user.password_hash = generate_password_hash(new_password)
        changes.append("password changed")

    db.session.commit()

    if changes:
        _log_audit(user.id, "update", "users", user.id, "; ".join(changes))
    return user


# ---------------------------------------------------------------------------
# إعادة تعيين المدير لكلمة مرور مستخدم آخر
# ---------------------------------------------------------------------------

def admin_reset_user_password(target_user_id, new_password, confirm_password, reset_by_id):
    target = db.session.get(User, target_user_id)
    if not target:
        raise ValueError("المستخدم غير موجود")

    _validate_new_password(new_password, confirm_password)

    target.password_hash = generate_password_hash(new_password)
    db.session.commit()

    _log_audit(reset_by_id, "update", "users", target.id, f"password reset by admin for {target.username}")
    return target


# ---------------------------------------------------------------------------
# نسيت كلمة المرور (لأي مستخدم مسجَّل له بريد إلكتروني، بما فيهم المدير)
# ---------------------------------------------------------------------------

def start_password_reset(email):
    """
    يبحث عن مستخدم بهذا البريد، يولّد رمز تفعيل ويرسله، ويعيد بيانات
    مؤقتة (تُخزَّن في session) لإتمام تغيير كلمة المرور بعد تأكيد الرمز.
    """
    email = _validate_email(email)

    user = User.query.filter_by(email=email).first()
    if not user:
        raise ValueError("لا يوجد حساب مسجَّل بهذا البريد الإلكتروني")

    if user.role == "inactive":
        raise ValueError("هذا الحساب معطَّل، تواصل مع المدير")

    code = f"{secrets.randbelow(1000000):06d}"

    try:
        send_verification_code(email, code)
    except EmailSendError as e:
        raise ValueError(str(e))

    return {
        "user_id": user.id,
        "email": email,
        "code": code,
        "generated_at": datetime.utcnow().isoformat(),
    }


def complete_password_reset(pending, entered_code, new_password, confirm_password):
    """يتحقق من الرمز، ثم يحدّث كلمة مرور المستخدم صاحب pending."""
    if not pending:
        raise ValueError("انتهت صلاحية عملية الاسترجاع، ابدأ من جديد")

    generated_at = datetime.fromisoformat(pending["generated_at"])
    if datetime.utcnow() - generated_at > timedelta(minutes=CODE_VALID_MINUTES):
        raise ValueError("انتهت صلاحية رمز التفعيل، اطلب رمزاً جديداً")

    if (entered_code or "").strip() != pending["code"]:
        raise ValueError("رمز التفعيل غير صحيح")

    _validate_new_password(new_password, confirm_password)

    user = db.session.get(User, pending["user_id"])
    if not user:
        raise ValueError("الحساب لم يعد موجوداً")

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()

    _log_audit(user.id, "update", "users", user.id, "password reset via forgot-password flow")
    return user
