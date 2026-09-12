"""
سكربت طوارئ لإعادة تعيين كلمة مرور أي حساب مباشرة من قاعدة البيانات.

يُستخدم فقط عندما لا يمكن استخدام "نسيت كلمة المرور" من الموقع (مثلاً:
حساب المدير لا يملك بريداً إلكترونياً مسجَّلاً). يتطلب وصولاً فعلياً
لملفات المشروع على الجهاز.

الاستخدام:
    python admin_password_reset.py
"""

from getpass import getpass
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User


def reset_password():
    app = create_app()

    with app.app_context():
        users = User.query.order_by(User.id.asc()).all()
        if not users:
            print("لا يوجد أي مستخدم في قاعدة البيانات.")
            return

        print("المستخدمون الحاليون:")
        for u in users:
            email_display = u.email or "بلا بريد"
            print(f"  - {u.username} ({u.role}) — {email_display}")

        username = input("\nاسم المستخدم الذي تريد إعادة تعيين كلمة مروره: ").strip()
        user = User.query.filter_by(username=username).first()

        if not user:
            print(f"لا يوجد مستخدم باسم '{username}'.")
            return

        password = getpass("كلمة المرور الجديدة: ")
        confirm = getpass("تأكيد كلمة المرور الجديدة: ")

        if not password or len(password) < 6:
            print("كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
            return

        if password != confirm:
            print("كلمتا المرور غير متطابقتين. أعد المحاولة.")
            return

        user.password_hash = generate_password_hash(password)
        db.session.commit()

        print(f"\nتم تحديث كلمة مرور '{username}' بنجاح. يمكنك الآن تسجيل الدخول من /auth/login")
        if not user.email:
            print("تنبيه: هذا الحساب بلا بريد إلكتروني، لذا لن يعمل معه \"نسيت كلمة المرور\" مستقبلاً.")
            print("يُنصح بإضافة بريد له من صفحة \"حسابي\" بعد الدخول، لتفادي الحاجة لهذا السكربت مرة أخرى.")


if __name__ == "__main__":
    reset_password()

