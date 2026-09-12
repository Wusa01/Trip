from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.services.dashboard_service import get_dashboard_stats

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard_page():
    stats = get_dashboard_stats(current_user.role)
    return render_template("dashboard.html", stats=stats)
