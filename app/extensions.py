from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# كائنات مشتركة بين كل أجزاء التطبيق لتفادي الاستيراد الدائري
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "الرجاء تسجيل الدخول للوصول إلى هذه الصفحة"
