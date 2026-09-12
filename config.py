import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "tribe.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # إعدادات رفع الصور
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 ميجابايت لكل صورة
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

    # اللغة الافتراضية للواجهة
    DEFAULT_LOCALE = "ar"

    # إعدادات إرسال البريد (Gmail SMTP) — لرمز التفعيل والنسخ الاحتياطية
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")            # بريد Gmail الكامل
    MAIL_APP_PASSWORD = os.environ.get("MAIL_APP_PASSWORD")    # كلمة مرور تطبيقات من 16 خانة
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)
