"""Filter-aware reports, with identical authorization and populations to the screen."""

import csv
import io
from datetime import date
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from .analytics import record_view, scoped_rows


TITLES = {"executive": "Executive Summary Report", "regional": "Regional Performance Report",
          "area": "Area Profiling Report", "team": "Team Performance Report", "outstanding": "Outstanding Monitoring Report"}
DEFINITION = "Unique = PAM ID kohort survei; konflik geografis dikecualikan. Status konflik tidak diasumsikan selesai. Potensi/sisa = master snapshot seluruh periode, geografis saja; bukan kohort survei."


def report_table(kind, analysis, data, prepared, filters, store, role):
    metrics = analysis["metrics"]
    if kind == "executive":
        return ["Metric", "Value", "Definition"], [
            ["Potential", analysis["master"]["potential"], analysis["master"]["scope"]],
            ["Unique canvassed", metrics["canvassed"], analysis["scope"]["cohort"]],
            ["Unique interested", metrics["interested"], "Consistent interested status within selected survey cohort"],
            ["Unique installed", metrics["installed"], "Interested cohort; consistent Done status"],
            ["Remaining potential", analysis["master"]["remaining"], "Master minus matched interested; all-period stock"],
            ["Interest conversion", metrics["interest_rate"], "Unique interested / unique canvassed; fraction"],
            ["Installation conversion", metrics["installation_rate"], "Unique installed / unique interested; fraction"],
            ["Target achievement", analysis["target"].get("achievement"), analysis["target"]["reason"]]]
    if kind in ("regional", "area"):
        entries = analysis["regions" if kind == "regional" else "areas"]
        headers = ["Region" if kind == "regional" else "Area", "Master potential", "Unique canvassed", "Unique interested", "Unique installed", "Remaining master", "Installation rate"]
        if kind == "area":
            headers.extend(["Priority", "Evidence / action"])
        rows = [[entry[key] for key in ("name", "potential", "canvassed", "interested", "installed", "remaining", "installation_rate")]
                + ([entry["priority"], entry["reason"]] if kind == "area" else []) for entry in entries]
        return headers, rows
    if kind == "team":
        return ["Coordinator", "Surveyors with activity", "Active surveyors", "Unique canvassed", "Unique interested", "Unique installed", "Observed surveyor-days", "Interested / observed day"], [
            [entry[key] for key in ("name", "surveyors_with_activity", "active_surveyors", "canvassed", "interested", "installed", "observed_surveyor_days", "interested_per_observed_day")]
            for entry in analysis["teams"]]
    if role != "owner":
        return ["Source installation status", "Outstanding survey rows"], list(analysis["outstanding"]["by_status"].items())
    overrides = store.latest("mapping").get("all", {})
    actions = store.latest("followup")
    selected = scoped_rows(data, prepared, filters, overrides)
    rows = []
    for row in selected:
        if row["interest"] and not row["installed"] and not row["cancelled"]:
            entry = record_view(data, prepared, row, overrides, actions.get(row["ref"]))
            action = entry["followup"] or {}
            rows.append([entry["ref"], entry["pam"], entry["regional"], entry["area"], entry["status"],
                         entry["coordinator"], action.get("pic", ""), action.get("target_date", ""), action.get("action", ""),
                         action.get('status','Not recorded'),action.get('resolution_notes',''),action.get('case_started',''),action.get('pause_days',0),
                         'Resolved since import' if action.get('status','').casefold() in ('done','cancel') else 'Active',
                         aging_value(action,date.fromisoformat(analysis['outstanding']['aging_as_of']))])
    return ["Case reference", "PAM ID", "Region", "Area", "Source status", "Coordinator", "Follow-up PIC", "Target date", "Latest action",
            'Follow-up status','Resolution notes','Confirmed case start','Verified pause days','Operational state','Active aging days'], rows


def aging_value(action,today):
    if action.get('status','').casefold() in ('done','cancel'):
        return 'Resolved since import'
    return max(0,(today-date.fromisoformat(action['case_started'])).days-action.get('pause_days',0)) if action.get('case_started') else 'Insufficient Data'


def filter_labels(data,filters):
    area,kel=int(filters.get('ab',-1)),int(filters.get('kel',-1))
    return ' | '.join([
        'Regional: '+(filters.get('reg') or 'All'),
        'Area: '+(data['abs'][area] if area>=0 else 'All'),
        'Kelurahan: '+(data['kels'][kel] if kel>=0 else 'All'),
        'Coordinator: '+(filters.get('coordinator') or 'All'),
        'Source status: '+(', '.join(filters.get('statuses',[])) or 'All')])


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


def make_report(kind, extension, analysis, data, prepared, filters, store, role, source):
    headers, rows = report_table(kind, analysis, data, prepared, filters, store, role)
    if len(rows) > (2000 if extension == "pdf" else 20000):
        raise ValueError("Laporan terlalu besar; persempit filter sebelum ekspor. Tidak ada baris yang dipotong diam-diam.")
    scope = analysis["scope"]
    metadata = [TITLES[kind], f"Survey period: {scope['start'] or 'all available through'} – {scope['end']}",
                "Filters: " + filter_labels(data,filters), "Last successful import: " + (source.get("imported_at") or "Insufficient Data"),
                "Source loaded at: " + source["loaded_at"], "Source fingerprint: " + source["fingerprint"],
                DEFINITION, scope["history"], "Role: " + role]
    if extension == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        for item in metadata:
            writer.writerow([safe_cell(item)])
        writer.writerow([])
        writer.writerow(headers)
        writer.writerows([[safe_cell(value) for value in row] for row in rows])
        return output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
    if extension == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Report"
        for item in metadata:
            sheet.append([item])
        sheet.append([])
        sheet.append(headers)
        header_row = sheet.max_row
        for cell in sheet[header_row]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = PatternFill("solid", fgColor="142B49")
        for row in rows:
            sheet.append(row)
        # Source strings are literal text, even when they resemble spreadsheet formulas.
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        sheet.freeze_panes = f"A{header_row + 1}"
        sheet.auto_filter.ref = f"A{header_row}:{sheet.cell(sheet.max_row, len(headers)).coordinate}"
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(48, max(16, len(str(headers[column[0].column - 1])) + 2)) if column[0].column <= len(headers) else 16
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 8
    styles["BodyText"].leading = 11
    document = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=30)
    content = [Paragraph(escape(metadata[0]), styles["Title"])]
    content.extend(Paragraph(escape(item), styles["BodyText"]) for item in metadata[1:])
    content.append(Spacer(1, 14))
    cells = [[Paragraph(escape(str(value if value is not None else "Insufficient Data")), styles["BodyText"]) for value in row] for row in [headers, *rows]]
    table = LongTable(cells, repeatRows=1, splitInRow=1, colWidths=[(landscape(A4)[0] - 48) / len(headers)] * len(headers))
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EFF5")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                               ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DEE5ED"))]))
    content.append(table)
    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(landscape(A4)[0] - 24, 16, f"PMO RPD | Page {doc.page}")
    document.build(content, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue(), "application/pdf"
