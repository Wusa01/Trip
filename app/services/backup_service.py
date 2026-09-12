import os
import shutil
import sqlite3
from datetime import datetime

from flask import current_app

from app.extensions import db
from app.services.relation_service import _log_audit
from app.services.email_service import send_backup_email, EmailSendError


class BackupError(Exception):
    """يُرفع عند فشل أي عملية نسخ احتياطي أو استيراد، برسالة عربية جاهزة."""
    pass


# ---------------------------------------------------------------------------
# تحديد مسار ملف قاعدة البيانات الحالي
# ---------------------------------------------------------------------------

def get_db_path():
    db_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not db_uri.startswith("sqlite:///"):
        raise BackupError("النسخ الاحتياطي والاستيراد مدعومان فقط لقواعد بيانات SQLite المحلية")

    db_path = db_uri.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        raise BackupError("ملف قاعدة البيانات غير موجود")
    return db_path


def _auto_backups_dir():
    base_dir = os.path.dirname(get_db_path())
    backups_dir = os.path.join(base_dir, "auto_backups")
    os.makedirs(backups_dir, exist_ok=True)
    return backups_dir


# ---------------------------------------------------------------------------
# إرسال نسخة احتياطية بالبريد
# ---------------------------------------------------------------------------

def send_backup_to_email(to_email, sent_by_id):
    db_path = get_db_path()
    label = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        send_backup_email(to_email, db_path, label)
    except EmailSendError as e:
        raise BackupError(str(e))

    _log_audit(sent_by_id, "create", "backup_email", 0, f"sent to {to_email} at {label}")


# ---------------------------------------------------------------------------
# نسخة احتياطية تلقائية قبل الاستيراد
# ---------------------------------------------------------------------------

def create_auto_backup():
    """
    ينسخ ملف قاعدة البيانات الحالي إلى instance/auto_backups/ بختم وقت،
    قبل أي عملية استيراد تستبدل البيانات — للحماية من استيراد خاطئ.
    """
    db_path = get_db_path()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = os.path.join(_auto_backups_dir(), f"before_import_{timestamp}.db")

    shutil.copy2(db_path, backup_path)
    return backup_path


# ---------------------------------------------------------------------------
# استيراد (استبدال) قاعدة البيانات بالكامل من ملف مرفوع
# ---------------------------------------------------------------------------

def _looks_like_valid_backup(file_path):
    """تحقق سريع: هل الملف قاعدة بيانات SQLite تحتوي جدول users؟"""
    try:
        conn = sqlite3.connect(file_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        found = cur.fetchone() is not None
        conn.close()
        return found
    except sqlite3.Error:
        return False


def import_database(file_storage, imported_by_id):
    """
    يستبدل قاعدة البيانات الحالية بالكامل بملف مرفوع، بعد أخذ نسخة
    احتياطية تلقائية من الحالية أولاً. يُنهي كل اتصالات SQLAlchemy
    الحالية قبل الاستبدال لتفادي تلف الملف.

    تنبيه: بعد نجاح الاستيراد يجب تسجيل خروج المستخدم الحالي فوراً من
    الـ route المستدعي، لأن جدول المستخدمين نفسه قد استُبدل.
    """
    if not file_storage or file_storage.filename == "":
        raise BackupError("لم يتم اختيار ملف")

    if not file_storage.filename.lower().endswith(".db"):
        raise BackupError("الملف يجب أن يكون بصيغة .db")

    db_path = get_db_path()

    temp_path = db_path + ".uploaded_tmp"
    file_storage.save(temp_path)

    if not _looks_like_valid_backup(temp_path):
        os.remove(temp_path)
        raise BackupError("الملف المرفوع لا يبدو نسخة قاعدة بيانات صالحة لهذا النظام")

    backup_path = create_auto_backup()

    _log_audit(imported_by_id, "update", "database_import", 0,
               f"database replaced from upload, auto-backup at {backup_path}")

    try:
        db.session.remove()
        db.engine.dispose()
        shutil.move(temp_path, db_path)
    except OSError as e:
        raise BackupError(f"تعذّر استبدال قاعدة البيانات: {e}")

    return backup_path
