from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from datetime import datetime
import os
from io import BytesIO

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from flask import current_app

FONT_REGULAR = "Amiri"
FONT_BOLD = "Amiri-Bold"

_fonts_registered = False


def _register_fonts():
    """تسجيل خط Amiri مرة واحدة فقط لكل عملية تشغيل للتطبيق"""
    global _fonts_registered
    if _fonts_registered:
        return

    fonts_dir = os.path.join(current_app.root_path, "static", "fonts")
    regular_path = os.path.join(fonts_dir, "Amiri-Regular.ttf")
    bold_path = os.path.join(fonts_dir, "Amiri-Bold.ttf")

    if not os.path.exists(regular_path):
        raise FileNotFoundError(
            "ملف الخط Amiri-Regular.ttf غير موجود في app/static/fonts/ — "
            "يجب تحميله ووضعه هناك قبل توليد أي PDF"
        )

    pdfmetrics.registerFont(TTFont(FONT_REGULAR, regular_path))

    if os.path.exists(bold_path):
        pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
    else:
        # في حال عدم توفر الخط الغامق، نستخدم العادي بدلاً منه لتفادي توقف التوليد
        pdfmetrics.registerFont(TTFont(FONT_BOLD, regular_path))

    _fonts_registered = True


def shape_arabic(text):
    """
    يهيّئ النص العربي للعرض الصحيح في PDF: إعادة تشكيل الحروف المتصلة
    (arabic_reshaper) ثم ضبط اتجاه القراءة من اليمين لليسار (bidi).
    يُطبَّق دائماً على أي نص عربي قبل رسمه على الصفحة.
    """
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def _draw_rtl_line(c, text, x_right, y, font=FONT_REGULAR, size=12):
    """يرسم سطراً عربياً محاذىً لليمين عند الإحداثية x_right"""
    c.setFont(font, size)
    c.drawRightString(x_right, y, shape_arabic(text))


# ---------------------------------------------------------------------------
# بطاقة شخصية PDF
# ---------------------------------------------------------------------------

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm

INK = HexColor("#1E2A24")
PARCHMENT = HexColor("#EAE2CF")
PAPER = HexColor("#F6F2E6")
BRASS = HexColor("#A8823C")
LINE_GRAY = HexColor("#C9BFA0")

ORDINALS_AR = ["الأولى", "الثانية", "الثالثة", "الرابعة", "الخامسة",
               "السادسة", "السابعة", "الثامنة", "التاسعة", "العاشرة"]


def generate_person_card_pdf(person, father, mother, maternal_tribe, children, spouses_with_children):
    """
    بطاقة احترافية بجداول حقيقية: صورة + اسم كامل في الأعلى، صندوق الأم/الأخوال،
    ثم لكل زوجة قسم مستقل بعنوانها وعشيرتها وجدولين متجاورين (ذكور/إناث).
    """
    _register_fonts()

    buffer = BytesIO()
    page_w, page_h = A4
    margin = 16 * mm
    header_h = 26 * mm
    footer_h = 12 * mm
    content_w = page_w - 2 * margin

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=margin, leftMargin=margin,
        topMargin=header_h + 10 * mm, bottomMargin=footer_h + 12 * mm,
    )

    # --- الأنماط النصية ---
    name_style = ParagraphStyle("name", fontName=FONT_BOLD, fontSize=18, alignment=TA_RIGHT, textColor=INK, leading=23)
    sub_style = ParagraphStyle("sub", fontName=FONT_REGULAR, fontSize=10.5, alignment=TA_RIGHT, textColor=BRASS, leading=15)
    section_style = ParagraphStyle("section", fontName=FONT_BOLD, fontSize=12.5, alignment=TA_RIGHT, textColor=INK, spaceBefore=2, spaceAfter=2)
    info_style = ParagraphStyle("info", fontName=FONT_REGULAR, fontSize=10, alignment=TA_RIGHT, textColor=INK, leading=15)
    table_header_style = ParagraphStyle("th", fontName=FONT_BOLD, fontSize=9.5, alignment=TA_CENTER, textColor=PARCHMENT)
    table_cell_style = ParagraphStyle("td", fontName=FONT_REGULAR, fontSize=9.5, alignment=TA_RIGHT, textColor=INK, leading=13)
    empty_style = ParagraphStyle("empty", fontName=FONT_REGULAR, fontSize=9, alignment=TA_CENTER, textColor=LINE_GRAY)

    def P(text, style):
        return Paragraph(shape_arabic(text), style)

    story = []

    # -----------------------------------------------------------------
    # الصورة + الاسم الكامل
    # -----------------------------------------------------------------
    photo_w, photo_h = 32 * mm, 38 * mm

    if person.photo_path:
        photo_full_path = os.path.join(current_app.root_path, "static", person.photo_path)
        photo_flowable = RLImage(photo_full_path, width=photo_w - 4, height=photo_h - 4) \
            if os.path.exists(photo_full_path) else P("بدون صورة", empty_style)
    else:
        photo_flowable = P("بدون صورة", empty_style)

    photo_cell = Table([[photo_flowable]], colWidths=[photo_w], rowHeights=[photo_h])
    photo_cell.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, BRASS),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
    ]))

    name_lines = [P(person.full_name, name_style)]
    if person.tribe:
        name_lines.append(P(f"عشيرة: {person.tribe.tribe_name}", sub_style))
    name_lines.append(P("ذكر" if person.gender == "male" else "أنثى", sub_style))

    name_info_w = content_w - photo_w - 6 * mm
    name_info = Table([[x] for x in name_lines], colWidths=[name_info_w])
    name_info.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    header_row = Table([[name_info, photo_cell]], colWidths=[name_info_w, photo_w])
    header_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(header_row)
    story.append(Spacer(1, 10 * mm))

    # -----------------------------------------------------------------
    # صندوق الأم والأخوال
    # -----------------------------------------------------------------
    story.append(P("الأم والأخوال", section_style))
    story.append(Spacer(1, 3))

    mother_lines = [P(f"الأم: {mother.full_name if mother else 'غير مسجَّلة'}", info_style)]
    if maternal_tribe:
        mother_lines.append(P(f"الأخوال (عشيرة الأم): {maternal_tribe}", info_style))
    elif mother:
        mother_lines.append(P("الأخوال: عشيرة الأم غير مسجَّلة", empty_style))
    if father:
        mother_lines.append(P(f"الأب: {father.full_name}", info_style))

    mother_table = Table([[x] for x in mother_lines], colWidths=[content_w])
    mother_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, 0), (-1, -1), PARCHMENT),
        ("BOX", (0, 0), (-1, -1), 0.8, LINE_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(mother_table)
    story.append(Spacer(1, 10 * mm))

    # -----------------------------------------------------------------
    # جدول ذكور/إناث لقائمة أبناء واحدة
    # -----------------------------------------------------------------
    def build_gender_table(people_list, header_text):
        rows = [[P(header_text, table_header_style)]]
        if people_list:
            for p in people_list:
                rows.append([P(p.full_name, table_cell_style)])
        else:
            rows.append([P("لا يوجد", empty_style)])

        col_w = (content_w - 6 * mm) / 2
        t = Table(rows, colWidths=[col_w])

        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("BOX", (0, 0), (-1, -1), 0.8, LINE_GRAY),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (0, 1), (-1, -1), "RIGHT"),
            ("RIGHTPADDING", (0, 1), (-1, -1), 8),
        ]
        for i in range(1, len(rows)):
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), PARCHMENT if i % 2 == 0 else PAPER))
        t.setStyle(TableStyle(style_cmds))
        return t

    def build_children_row(sons, daughters):
        """البنات في العمود الأيسر، الأبناء في العمود الأيمن (يُقرأ أولاً في RTL)"""
        sons_table = build_gender_table(sons, "الأبناء (ذكور)")
        daughters_table = build_gender_table(daughters, "البنات (إناث)")
        col_w = (content_w - 6 * mm) / 2
        wrapper = Table([[daughters_table, sons_table]], colWidths=[col_w, col_w])
        wrapper.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return wrapper

    # -----------------------------------------------------------------
    # قسم مستقل لكل زوجة: عنوانها + جدولا ذكور/إناث
    # -----------------------------------------------------------------
    if spouses_with_children:
        for idx, item in enumerate(spouses_with_children):
            spouse = item["spouse"]
            spouse_children = item["children"]
            sons = [c for c in spouse_children if c.gender == "male"]
            daughters = [c for c in spouse_children if c.gender == "female"]

            ordinal = ORDINALS_AR[idx] if idx < len(ORDINALS_AR) else f"رقم {idx + 1}"
            tribe_txt = f" — عشيرتها: {spouse.tribe.tribe_name}" if spouse.tribe else ""
            status_txt = "" if item["marriage_status"] == "current" else (
                " (مطلَّقة)" if item["marriage_status"] == "divorced" else " (متوفاة)"
            )
            heading = f"الزوجة {ordinal}: {spouse.full_name}{tribe_txt}{status_txt}"

            section = [
                P(heading, section_style),
                Spacer(1, 3),
                build_children_row(sons, daughters),
                Spacer(1, 9 * mm),
            ]
            story.append(KeepTogether(section))
    else:
        story.append(P("لا توجد زوجات مسجَّلات", empty_style))
        story.append(Spacer(1, 6 * mm))

    # -----------------------------------------------------------------
    # أبناء غير مرتبطين بأي زواج مسجَّل (حالة نادرة، للاكتمال فقط)
    # -----------------------------------------------------------------
    spouse_children_ids = set()
    for item in spouses_with_children:
        spouse_children_ids.update(c.id for c in item["children"])
    leftover = [c for c in children if c.id not in spouse_children_ids]

    if leftover:
        sons = [c for c in leftover if c.gender == "male"]
        daughters = [c for c in leftover if c.gender == "female"]
        story.append(P("أبناء بدون زواج مسجَّل", section_style))
        story.append(Spacer(1, 3))
        story.append(build_children_row(sons, daughters))

    # -----------------------------------------------------------------
    # الإطار الزخرفي، الختم، والتذييل — يُرسم في كل صفحة تلقائياً
    # -----------------------------------------------------------------
    status_labels = {"approved": "معتمد", "pending": "قيد المراجعة", "rejected": "مرفوض"}

    def draw_decor(canvas_obj, _doc):
        canvas_obj.saveState()

        canvas_obj.setStrokeColor(BRASS)
        canvas_obj.setLineWidth(1.2)
        canvas_obj.rect(margin - 8, margin - 8, page_w - 2 * (margin - 8), page_h - 2 * (margin - 8))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.rect(margin - 4, margin - 4, page_w - 2 * (margin - 4), page_h - 2 * (margin - 4))

        canvas_obj.setFillColor(INK)
        canvas_obj.rect(margin - 8, page_h - margin - header_h + 8, page_w - 2 * (margin - 8), header_h, fill=1, stroke=0)

        canvas_obj.setFillColor(PARCHMENT)
        canvas_obj.setFont(FONT_BOLD, 15)
        canvas_obj.drawRightString(page_w - margin, page_h - margin - 10, shape_arabic("بطاقة تعريف شخصية"))
        canvas_obj.setFont(FONT_REGULAR, 9)
        canvas_obj.drawRightString(page_w - margin, page_h - margin - 20, shape_arabic("سجل العشيرة الرقمي"))

        seal_cx = margin + 11 * mm
        seal_cy = page_h - margin - header_h / 2 + 8
        seal_r = 9 * mm
        canvas_obj.setStrokeColor(BRASS)
        canvas_obj.setLineWidth(1)
        canvas_obj.circle(seal_cx, seal_cy, seal_r, fill=0, stroke=1)
        canvas_obj.setDash(1.5, 2)
        canvas_obj.circle(seal_cx, seal_cy, seal_r - 2.5, fill=0, stroke=1)
        canvas_obj.setDash()
        canvas_obj.setFillColor(PARCHMENT)
        canvas_obj.setFont(FONT_BOLD, 8)
        canvas_obj.drawCentredString(seal_cx, seal_cy - 2, person.public_id)

        canvas_obj.setStrokeColor(BRASS)
        canvas_obj.setLineWidth(0.6)
        canvas_obj.line(margin, margin + footer_h - 2, page_w - margin, margin + footer_h - 2)
        canvas_obj.setFillColor(INK)
        canvas_obj.setFont(FONT_REGULAR, 8)
        canvas_obj.drawRightString(page_w - margin, margin + 3, shape_arabic(f"تاريخ الإصدار: {datetime.now().strftime('%Y-%m-%d')}"))
        canvas_obj.drawString(margin, margin + 3, shape_arabic(f"الحالة: {status_labels.get(person.status, person.status)}"))
        canvas_obj.drawCentredString(page_w / 2, margin + 3, shape_arabic(f"صفحة {canvas_obj.getPageNumber()}"))

        canvas_obj.restoreState()

    doc.build(story, onFirstPage=draw_decor, onLaterPages=draw_decor)
    buffer.seek(0)
    return buffer

    # --- أقسام العائلة (والدان / أبناء / إخوة) في صناديق أفقية ---
    def draw_family_box(x0, box_w, title, people, y0, box_h):
        c.setFillColor(PARCHMENT)
        c.setStrokeColor(LINE_GRAY)
        c.rect(x0, y0 - box_h, box_w, box_h, fill=1, stroke=1)
        c.setFillColor(BRASS)
        c.setFont(FONT_BOLD, 9.5)
        c.drawRightString(x0 + box_w - 5, y0 - 12, shape_arabic(title))

        ty = y0 - 22
        c.setFillColor(INK)
        c.setFont(FONT_REGULAR, 8.5)
        if people:
            for p in people[:6]:
                c.drawRightString(x0 + box_w - 5, ty, shape_arabic(f"• {p.full_name}"))
                ty -= 11
        else:
            c.setFillColor(LINE_GRAY)
            c.drawRightString(x0 + box_w - 5, ty, shape_arabic("لا يوجد"))

    box_h = 42 * mm
    col_w = (right - left - 12) / 3
    draw_family_box(right - col_w, col_w, "الوالدان", parents, y, box_h)
    draw_family_box(right - 2 * col_w - 6, col_w, "الأبناء", children, y, box_h)
    draw_family_box(left, col_w, "الإخوة", siblings, y, box_h)

    # --- تذييل: تاريخ الإصدار + شارة الحالة ---
    footer_y = margin + 8
    c.setStrokeColor(BRASS)
    c.setLineWidth(0.6)
    c.line(left, footer_y + 10, right, footer_y + 10)

    status_labels = {"approved": "معتمد", "pending": "قيد المراجعة", "rejected": "مرفوض"}
    c.setFillColor(INK)
    c.setFont(FONT_REGULAR, 8)
    c.drawRightString(right, footer_y, shape_arabic(f"تاريخ الإصدار: {datetime.now().strftime('%Y-%m-%d')}"))
    c.drawString(left, footer_y, shape_arabic(f"الحالة: {status_labels.get(person.status, person.status)}"))

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# تقرير النسب PDF
# ---------------------------------------------------------------------------

def generate_lineage_report_pdf(chain):
    """chain: قائمة من get_lineage_report — من الشخص إلى الجد الأعلى"""
    _register_fonts()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    right_margin = width - 2 * 28
    y = height - 60

    _draw_rtl_line(c, "تقرير النسب", right_margin, y, font=FONT_BOLD, size=18)
    y -= 40

    for entry in chain:
        prefix = "→ " if entry["depth"] > 0 else ""
        _draw_rtl_line(c, f"{prefix}{entry['full_name']} ({entry['public_id']})", right_margin, y, size=13)
        y -= 26
        if y < 60:
            c.showPage()
            y = height - 60

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# تقرير عائلة (فرع) PDF
# ---------------------------------------------------------------------------

def generate_branch_report_pdf(report):
    _register_fonts()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    right_margin = width - 2 * 28
    y = height - 60

    root = report["root"]
    _draw_rtl_line(c, f"تقرير فرع: {root['full_name']}", right_margin, y, font=FONT_BOLD, size=18)
    y -= 40

    _draw_rtl_line(c, f"عدد الرجال: {report['males_count']}", right_margin, y, size=13)
    y -= 22
    _draw_rtl_line(c, f"عدد النساء: {report['females_count']}", right_margin, y, size=13)
    y -= 22
    _draw_rtl_line(c, f"إجمالي عدد الأفراد في الفرع: {report['total_count']}", right_margin, y, size=13)
    y -= 34

    if report["children"]:
        _draw_rtl_line(c, "الأبناء المباشرون:", right_margin, y, font=FONT_BOLD, size=13)
        y -= 20
        for ch in report["children"]:
            _draw_rtl_line(c, f"- {ch['full_name']}", right_margin - 15, y, size=11)
            y -= 18
            if y < 60:
                c.showPage()
                y = height - 60
        y -= 10

    if report["grandchildren"]:
        _draw_rtl_line(c, "الأحفاد:", right_margin, y, font=FONT_BOLD, size=13)
        y -= 20
        for g in report["grandchildren"]:
            _draw_rtl_line(c, f"- {g['full_name']}", right_margin - 15, y, size=11)
            y -= 18
            if y < 60:
                c.showPage()
                y = height - 60

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

