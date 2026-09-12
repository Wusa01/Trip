import os
from datetime import datetime
from flask import (
    Blueprint, request, jsonify, render_template, redirect, url_for,
    send_file, current_app, session, abort
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User
from app.services.auth_service import (
    no_users_exist,
    start_first_admin_signup,
    complete_first_admin_signup,
    update_own_profile,
    admin_reset_user_password,
    start_password_reset,
    complete_password_reset,
)
from app.services.backup_service import (
    send_backup_to_email,
    import_database,
    BackupError,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

SETUP_SESSION_KEY = "setup_pending"


# ---------------------------------------------------------------------------
# إنشاء أول حساب مدير (يظهر فقط إذا لم يوجد أي مستخدم بعد)
# ---------------------------------------------------------------------------

@auth_bp.route("/setup", methods=["GET"])
def setup_page():
    if not no_users_exist():
        return redirect(url_for("auth.login_page"))
    return render_template("setup.html")


@auth_bp.route("/setup/request-code", methods=["POST"])
def setup_request_code():
    if not no_users_exist():
        return jsonify({"error": "يوجد حساب مسجَّل بالفعل في النظام"}), 400

    username = request.form.get("username", "")
    email = request.form.get("email", "")
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    try:
        pending = start_first_admin_signup(username, email, password, confirm_password)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session[SETUP_SESSION_KEY] = pending
    return jsonify({"email": pending["email"]})


@auth_bp.route("/setup/confirm", methods=["POST"])
def setup_confirm():
    pending = session.get(SETUP_SESSION_KEY)
    code = request.form.get("code", "")

    try:
        user = complete_first_admin_signup(pending, code)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session.pop(SETUP_SESSION_KEY, None)
    login_user(user)
    return jsonify({"redirect": url_for("dashboard.dashboard_page")})


# ---------------------------------------------------------------------------
# تسجيل الدخول / الخروج
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET"])
def login_page():
    if no_users_exist():
        return redirect(url_for("auth.setup_page"))
    if current_user.is_authenticated:
        return redirect(url_for("person.search_page"))
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password_hash, password):
        return render_template("login.html", error="اسم المستخدم أو كلمة المرور غير صحيحة")

    login_user(user)
    return redirect(url_for("person.search_page"))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login_page"))


# ---------------------------------------------------------------------------
# نسيت كلمة المرور
# ---------------------------------------------------------------------------

FORGOT_SESSION_KEY = "forgot_password_pending"


@auth_bp.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    if current_user.is_authenticated:
        return redirect(url_for("person.search_page"))
    return render_template("forgot_password.html")


@auth_bp.route("/forgot-password/request-code", methods=["POST"])
def forgot_password_request_code():
    email = request.form.get("email", "")

    try:
        pending = start_password_reset(email)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session[FORGOT_SESSION_KEY] = pending
    return jsonify({"email": pending["email"]})


@auth_bp.route("/forgot-password/confirm", methods=["POST"])
def forgot_password_confirm():
    pending = session.get(FORGOT_SESSION_KEY)
    code = request.form.get("code", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    try:
        user = complete_password_reset(pending, code, new_password, confirm_password)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session.pop(FORGOT_SESSION_KEY, None)
    login_user(user)
    return jsonify({"redirect": url_for("person.search_page")})


# ---------------------------------------------------------------------------
# حسابي (لأي مستخدم مسجَّل دخوله)
# ---------------------------------------------------------------------------

@auth_bp.route("/profile", methods=["GET"])
@login_required
def profile_page():
    return render_template("profile.html")


@auth_bp.route("/profile/update", methods=["POST"])
@login_required
def api_update_profile():
    username = request.form.get("username", "")
    email = request.form.get("email", "")
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_new_password = request.form.get("confirm_new_password", "")

    try:
        update_own_profile(
            current_user, username, email, current_password,
            new_password, confirm_new_password,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"status": "updated"})


# ---------------------------------------------------------------------------
# إدارة المستخدمين (للمدير فقط)
# ---------------------------------------------------------------------------

@auth_bp.route("/users", methods=["GET"])
@login_required
def users_page():
    if current_user.role != "admin":
        return redirect(url_for("person.search_page"))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=users)


@auth_bp.route("/api/users/create", methods=["POST"])
@login_required
def api_create_user():
    if current_user.role != "admin":
        return jsonify({"error": "إنشاء المستخدمين للمدير فقط"}), 403

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip() or None
    password = request.form.get("password", "")
    role = request.form.get("role", "user")

    if not username or not password:
        return jsonify({"error": "اسم المستخدم وكلمة المرور إلزاميان"}), 400

    if role not in ("admin", "user", "researcher"):
        return jsonify({"error": "دور غير معروف"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "اسم المستخدم مستخدم بالفعل"}), 400

    if email and User.query.filter_by(email=email).first():
        return jsonify({"error": "البريد الإلكتروني مستخدم بالفعل"}), 400

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({"id": user.id, "username": user.username, "role": user.role}), 201


@auth_bp.route("/api/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
def api_deactivate_user(user_id):
    if current_user.role != "admin":
        return jsonify({"error": "غير مصرح"}), 403

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "المستخدم غير موجود"}), 404

    user.role = "inactive"
    db.session.commit()
    return jsonify({"id": user.id, "status": "deactivated"})


@auth_bp.route("/api/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
def api_reset_user_password(user_id):
    if current_user.role != "admin":
        return jsonify({"error": "إعادة تعيين كلمة المرور للمدير فقط"}), 403

    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    try:
        admin_reset_user_password(user_id, new_password, confirm_password, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": user_id, "status": "password_reset"})


# ---------------------------------------------------------------------------
# نسخ احتياطي لقاعدة البيانات (للمدير فقط)
# ---------------------------------------------------------------------------

@auth_bp.route("/backup", methods=["GET"])
@login_required
def download_backup():
    """
    يُنزّل نسخة كاملة من ملف قاعدة البيانات SQLite بتاريخ اليوم في اسم الملف.
    """
    if current_user.role != "admin":
        return "النسخ الاحتياطي للمدير فقط", 403

    db_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not db_uri.startswith("sqlite:///"):
        return "النسخ الاحتياطي مدعوم فقط لقواعد بيانات SQLite المحلية", 400

    db_path = db_uri.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        return "ملف قاعدة البيانات غير موجود", 404

    filename = f"نسخة_احتياطية_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.db"
    return send_file(db_path, as_attachment=True, download_name=filename)


@auth_bp.route("/backup/email", methods=["POST"])
@login_required
def api_backup_email():
    if current_user.role != "admin":
        return jsonify({"error": "النسخ الاحتياطي للمدير فقط"}), 403

    to_email = request.form.get("email", "").strip() or current_user.email
    if not to_email:
        return jsonify({"error": "لا يوجد بريد إلكتروني — أدخل بريداً أو أضِف بريدك من صفحة حسابي"}), 400

    try:
        send_backup_to_email(to_email, current_user.id)
    except BackupError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"status": "sent", "email": to_email})


@auth_bp.route("/backup/import", methods=["POST"])
@login_required
def api_backup_import():
    if current_user.role != "admin":
        return jsonify({"error": "استيراد البيانات للمدير فقط"}), 403

    confirmation = request.form.get("confirmation", "").strip()
    if confirmation != "نعم":
        return jsonify({"error": "يجب كتابة \"نعم\" لتأكيد استبدال كل البيانات الحالية"}), 400

    uploaded_file = request.files.get("backup_file")

    try:
        import_database(uploaded_file, current_user.id)
    except BackupError as e:
        return jsonify({"error": str(e)}), 400

    # جدول المستخدمين استُبدل بالكامل — يجب تسجيل الخروج فوراً
    logout_user()
    session.clear()

    return jsonify({
        "status": "imported",
        "redirect": url_for("auth.login_page"),
        "message": "تم استيراد البيانات بنجاح. سجّل الدخول الآن بالحساب الموجود في النسخة المستوردة.",
    })
