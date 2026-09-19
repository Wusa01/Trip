import os
import sqlite3
from flask import Flask, redirect, url_for
from app.extensions import db, login_manager
from app.models import User


def _ensure_email_column(app):
    """
    ترحيل تلقائي وخفيف: إذا كانت قاعدة البيانات موجودة مسبقاً من نسخة
    أقدم لا تحتوي عمود email في جدول users، يُضاف الآن تلقائياً — بدون
    الحاجة لحذف البيانات أو تشغيل أي أمر يدوي.
    """
    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if not db_uri.startswith("sqlite:///"):
        return

    db_path = db_uri.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        existing_columns = [row[1] for row in cur.fetchall()]

        if "email" not in existing_columns:
            cur.execute("ALTER TABLE users ADD COLUMN email VARCHAR(150)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email)")
            conn.commit()
    finally:
        conn.close()


def _ensure_person_type_column(app):
    """
    ترحيل تلقائي خفيف مماثل لـ _ensure_email_column: يضيف عمود person_type
    إلى جدول persons إن كانت قاعدة البيانات من نسخة أقدم لا تحتوي عليه
    (قبل إضافة ميزة "الأصدقاء والجيران"). جدول social_links الجديد
    يُنشأ تلقائياً عبر db.create_all() فلا يحتاج ترحيلاً يدوياً.
    """
    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if not db_uri.startswith("sqlite:///"):
        return

    db_path = db_uri.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(persons)")
        existing_columns = [row[1] for row in cur.fetchall()]

        if "person_type" not in existing_columns:
            cur.execute("ALTER TABLE persons ADD COLUMN person_type VARCHAR(20) NOT NULL DEFAULT 'family'")
            conn.commit()
    finally:
        conn.close()


def create_app(config_class="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.dirname(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes.auth_routes import auth_bp
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.person_routes import person_bp
    from app.routes.relation_routes import relation_bp
    from app.routes.tree_routes import tree_bp
    from app.routes.report_routes import report_bp
    from app.routes.relationship_routes import relationship_bp
    from app.routes.tribe_routes import tribe_bp
    from app.routes.social_routes import social_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(person_bp)
    app.register_blueprint(relation_bp)
    app.register_blueprint(tree_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(relationship_bp)
    app.register_blueprint(tribe_bp)
    app.register_blueprint(social_bp)

    with app.app_context():
        db.create_all()
        _ensure_email_column(app)
        _ensure_person_type_column(app)

    @app.context_processor
    def inject_locale():
        return {"locale": app.config.get("DEFAULT_LOCALE", "ar"), "dir": "rtl"}

    # ملاحظة: تم حذف auto_login الذي كان يُسجّل أي زائر تلقائياً كمدير
    # دون كلمة مرور (ثغرة أمنية خطيرة). تسجيل الدخول الآن إلزامي فعلياً
    # عبر auth_routes.py، ويحمي كل الصفحات المزخرَفة بـ @login_required.

    @app.route("/")
    def index():
        from app.services.auth_service import no_users_exist
        if no_users_exist():
            return redirect(url_for("auth.setup_page"))
        return redirect(url_for("dashboard.dashboard_page"))

    return app
