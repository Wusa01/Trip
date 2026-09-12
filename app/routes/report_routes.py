from flask import Blueprint, send_file, abort, render_template
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Person
from app.services.relation_service import get_father, get_mother, get_children, get_spouses_with_children
from app.services.tree_service import get_lineage_report, get_branch_report
from app.utils.pdf_generator import (
    generate_person_card_pdf,
    generate_lineage_report_pdf,
    generate_branch_report_pdf,
)

report_bp = Blueprint("report", __name__, url_prefix="/reports")


def _check_visible(person):
    if person.status != "approved" and current_user.role not in ("admin", "researcher"):
        abort(404)


def _build_person_card_pdf(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    _check_visible(person)

    father = get_father(person_id)
    mother = get_mother(person_id)
    maternal_tribe = mother.tribe.tribe_name if (mother and mother.tribe) else None
    children = get_children(person_id)
    spouses = get_spouses_with_children(person_id)

    return person, generate_person_card_pdf(person, father, mother, maternal_tribe, children, spouses)


# ---------------------------------------------------------------------------
# معاينة داخل المنصة قبل التصدير
# ---------------------------------------------------------------------------

@report_bp.route("/person/<int:person_id>/preview", methods=["GET"])
@login_required
def person_card_preview(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    _check_visible(person)

    return render_template("pdf_preview.html", person=person,
                            view_endpoint="report.person_card_pdf_view",
                            download_endpoint="report.person_card_pdf",
                            title="بطاقة تعريف شخصية")


@report_bp.route("/person/<int:person_id>/pdf/view", methods=["GET"])
@login_required
def person_card_pdf_view(person_id):
    """يُرجع نفس ملف PDF لكن للعرض المضمَّن داخل الصفحة، وليس كتنزيل إجباري"""
    try:
        person, buffer = _build_person_card_pdf(person_id)
    except FileNotFoundError as e:
        return str(e), 500

    return send_file(buffer, mimetype="application/pdf", as_attachment=False)


@report_bp.route("/person/<int:person_id>/pdf", methods=["GET"])
@login_required
def person_card_pdf(person_id):
    """التنزيل الفعلي — يُستدعى فقط من زر "تصدير" داخل صفحة المعاينة"""
    try:
        person, buffer = _build_person_card_pdf(person_id)
    except FileNotFoundError as e:
        return str(e), 500

    filename = f"{person.public_id}_بطاقة.pdf"
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)


# ---------------------------------------------------------------------------
# تقرير النسب — نفس نمط المعاينة قبل التصدير
# ---------------------------------------------------------------------------

@report_bp.route("/person/<int:person_id>/lineage/preview", methods=["GET"])
@login_required
def lineage_report_preview(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    _check_visible(person)

    return render_template("pdf_preview.html", person=person,
                            view_endpoint="report.lineage_report_pdf_view",
                            download_endpoint="report.lineage_report_pdf",
                            title="تقرير النسب")


@report_bp.route("/person/<int:person_id>/lineage/pdf/view", methods=["GET"])
@login_required
def lineage_report_pdf_view(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    _check_visible(person)

    try:
        chain = get_lineage_report(person_id)
        buffer = generate_lineage_report_pdf(chain)
    except FileNotFoundError as e:
        return str(e), 500
    except ValueError as e:
        return str(e), 404

    return send_file(buffer, mimetype="application/pdf", as_attachment=False)


@report_bp.route("/person/<int:person_id>/lineage/pdf", methods=["GET"])
@login_required
def lineage_report_pdf(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    _check_visible(person)

    try:
        chain = get_lineage_report(person_id)
        buffer = generate_lineage_report_pdf(chain)
    except FileNotFoundError as e:
        return str(e), 500
    except ValueError as e:
        return str(e), 404

    filename = f"{person.public_id}_تقرير_النسب.pdf"
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)


# ---------------------------------------------------------------------------
# تقرير الفرع — نفس نمط المعاينة قبل التصدير
# ---------------------------------------------------------------------------

@report_bp.route("/person/<int:person_id>/branch/preview", methods=["GET"])
@login_required
def branch_report_preview(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    _check_visible(person)

    return render_template("pdf_preview.html", person=person,
                            view_endpoint="report.branch_report_pdf_view",
                            download_endpoint="report.branch_report_pdf",
                            title="تقرير الفرع")


@report_bp.route("/person/<int:person_id>/branch/pdf/view", methods=["GET"])
@login_required
def branch_report_pdf_view(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    _check_visible(person)

    try:
        report = get_branch_report(person_id)
        buffer = generate_branch_report_pdf(report)
    except FileNotFoundError as e:
        return str(e), 500
    except ValueError as e:
        return str(e), 404

    return send_file(buffer, mimetype="application/pdf", as_attachment=False)


@report_bp.route("/person/<int:person_id>/branch/pdf", methods=["GET"])
@login_required
def branch_report_pdf(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        abort(404)
    _check_visible(person)

    try:
        report = get_branch_report(person_id)
        buffer = generate_branch_report_pdf(report)
    except FileNotFoundError as e:
        return str(e), 500
    except ValueError as e:
        return str(e), 404

    filename = f"{person.public_id}_تقرير_الفرع.pdf"
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)
