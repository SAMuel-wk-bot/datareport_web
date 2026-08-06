from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe_color(value, fallback):
    try:
        return colors.HexColor(value)
    except (ValueError, TypeError):
        return colors.HexColor(fallback)


def build_dataset_pdf(df, title, owner, primary="#6F2DBD", secondary="#B58CFF", orientation="portrait"):
    buffer = BytesIO()
    page_size = landscape(A4) if orientation == "landscape" else A4
    doc = SimpleDocTemplate(buffer, pagesize=page_size, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    primary_color = _safe_color(primary, "#6F2DBD")
    secondary_color = _safe_color(secondary, "#B58CFF")
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=primary_color, alignment=TA_CENTER, spaceAfter=9 * mm))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", textColor=primary_color, spaceBefore=5 * mm, spaceAfter=3 * mm))
    styles.add(ParagraphStyle(name="TableHeader", parent=styles["BodyText"], fontName="Helvetica-Bold", textColor=colors.white, fontSize=8))
    story = [Paragraph("DATAREPORT | REPORTE ANALÍTICO", styles["Normal"]), Spacer(1, 5 * mm), Paragraph(title, styles["ReportTitle"]), Paragraph(f"Preparado para {owner} | {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]), Spacer(1, 7 * mm)]
    metrics = [["Registros", f"{len(df):,}"], ["Columnas", str(len(df.columns))], ["Valores vacíos", f"{int(df.isna().sum().sum()):,}"], ["Duplicados", f"{int(df.duplicated().sum()):,}"]]
    metric_table = Table(metrics, colWidths=[45 * mm, 35 * mm], hAlign="CENTER")
    metric_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), primary_color), ("TEXTCOLOR", (0, 0), (0, -1), colors.white), ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#F5F0FA")), ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#DED3EA")), ("PADDING", (0, 0), (-1, -1), 8)]))
    story.extend([Paragraph("Resumen ejecutivo", styles["Section"]), metric_table, Spacer(1, 7 * mm), Paragraph("Vista previa de los datos", styles["Section"])])
    preview = df.head(25).copy().fillna("Sin dato")
    preview = preview.iloc[:, :(8 if orientation == "landscape" else 6)]
    rows = [[Paragraph(str(col), styles["TableHeader"]) for col in preview.columns]] + [[Paragraph(value[:45], styles["BodyText"]) for value in values] for values in preview.astype(str).values.tolist()]
    table = Table(rows, repeatRows=1, hAlign="CENTER")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), primary_color), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F5FB")]), ("GRID", (0, 0), (-1, -1), .35, secondary_color), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 7), ("PADDING", (0, 0), (-1, -1), 4)]))
    story.append(table)
    if len(df) > 25:
        story.extend([Spacer(1, 4 * mm), Paragraph(f"La vista muestra 25 de {len(df):,} registros.", styles["Normal"])])
    doc.build(story)
    buffer.seek(0)
    return buffer
