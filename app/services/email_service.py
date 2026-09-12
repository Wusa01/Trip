"""
خدمة إرسال البريد الإلكتروني عبر Gmail SMTP.
تُستخدم لغرضين: إرسال رمز تفعيل عند إنشاء حساب، وإرسال نسخة قاعدة
البيانات الاحتياطية كمرفق. الإعدادات (المستخدم، كلمة مرور التطبيقات)
تُقرأ من app.config التي تُعبَّأ من ملف .env في config.py.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from flask import current_app


class EmailSendError(Exception):
    """يُرفع عند فشل الإرسال، مع رسالة عربية جاهزة للعرض للمستخدم."""
    pass


def _build_message(to_email, subject, body_text, attachment_path=None):
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    if attachment_path:
        filename = os.path.basename(attachment_path)
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    return msg


def send_email(to_email, subject, body_text, attachment_path=None):
    """
    يرسل رسالة عبر Gmail SMTP. يرفع EmailSendError برسالة عربية واضحة
    عند أي فشل (إعدادات ناقصة، بيانات دخول خاطئة، انقطاع اتصال...).
    """
    username = current_app.config.get("MAIL_USERNAME")
    app_password = current_app.config.get("MAIL_APP_PASSWORD")
    server_host = current_app.config.get("MAIL_SERVER", "smtp.gmail.com")
    server_port = current_app.config.get("MAIL_PORT", 587)

    if not username or not app_password:
        raise EmailSendError(
            "إعدادات البريد الإلكتروني غير مكتملة على الخادم (MAIL_USERNAME / MAIL_APP_PASSWORD في .env)"
        )

    msg = _build_message(to_email, subject, body_text, attachment_path)

    try:
        with smtplib.SMTP(server_host, server_port, timeout=20) as server:
            server.starttls()
            server.login(username, app_password)
            server.sendmail(username, [to_email], msg.as_string())
    except smtplib.SMTPAuthenticationError:
        raise EmailSendError(
            "تعذّر تسجيل الدخول إلى بريد الإرسال — تأكد أن MAIL_APP_PASSWORD صحيحة (كلمة مرور تطبيقات وليست كلمة المرور العادية)"
        )
    except (smtplib.SMTPException, OSError) as e:
        raise EmailSendError(f"تعذّر إرسال البريد: {e}")


# ---------------------------------------------------------------------------
# رسائل جاهزة بصياغة عربية
# ---------------------------------------------------------------------------

def send_verification_code(to_email, code):
    subject = "رمز تفعيل حسابك — سجل العشيرة الرقمي"
    body = (
        f"مرحباً،\n\n"
        f"رمز تفعيل حسابك هو: {code}\n\n"
        f"أدخل هذا الرمز في صفحة إنشاء الحساب لإتمام التسجيل.\n"
        f"إذا لم تطلب إنشاء حساب، يمكنك تجاهل هذه الرسالة.\n"
    )
    send_email(to_email, subject, body)


def send_backup_email(to_email, db_file_path, backup_label):
    subject = f"نسخة احتياطية — سجل العشيرة الرقمي ({backup_label})"
    body = (
        f"مرحباً،\n\n"
        f"مرفق مع هذه الرسالة نسخة احتياطية كاملة من قاعدة بيانات سجل العشيرة، "
        f"بتاريخ {backup_label}.\n\n"
        f"احتفظ بهذا الملف في مكان آمن — يمكن استخدامه لاستعادة كل البيانات "
        f"من صفحة \"إدارة المستخدمين\" في المنصة عند الحاجة.\n"
    )
    send_email(to_email, subject, body, attachment_path=db_file_path)
