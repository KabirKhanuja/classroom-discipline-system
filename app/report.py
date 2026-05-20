"""PDF report generation (presentation-only). Takes already-computed data and
returns PDF bytes. No ThingSpeak / camera / Streamlit logic lives here."""

import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
	Image,
	PageBreak,
	Paragraph,
	SimpleDocTemplate,
	Spacer,
	Table,
	TableStyle,
)

REPORT_TITLE = "Smart Classroom Discipline Monitoring"

BLUE = colors.HexColor("#1D4ED8")
ORANGE = colors.HexColor("#C2410C")
SLATE = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
LIGHT = colors.HexColor("#f1f5f9")
BORDER = colors.HexColor("#d8dee8")


def _styles() -> dict:
	base = getSampleStyleSheet()
	return {
		"title": ParagraphStyle(
			"ReportTitle", parent=base["Title"], fontSize=22, textColor=SLATE,
			spaceAfter=2, leading=26,
		),
		"subtitle": ParagraphStyle(
			"ReportSubtitle", parent=base["Normal"], fontSize=10, textColor=MUTED,
			spaceAfter=2,
		),
		"section": ParagraphStyle(
			"Section", parent=base["Heading2"], fontSize=13, textColor=BLUE,
			spaceBefore=14, spaceAfter=6,
		),
		"body": ParagraphStyle("Body", parent=base["Normal"], fontSize=10, textColor=SLATE),
		"footer": ParagraphStyle(
			"Footer", parent=base["Normal"], fontSize=8, textColor=MUTED, alignment=TA_CENTER,
		),
	}


def _fig_to_png(fig) -> bytes:
	buf = io.BytesIO()
	fig.savefig(buf, format="png", bbox_inches="tight")
	plt.close(fig)
	buf.seek(0)
	return buf.getvalue()


def _trend_png(history_df: pd.DataFrame, threshold: int) -> bytes | None:
	if history_df is None or history_df.empty:
		return None

	fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=150)
	ax.plot(history_df["time"], history_df["sid1"], color="#1D4ED8", linewidth=1.8, label="Sid1 (Left)")
	ax.plot(history_df["time"], history_df["sid2"], color="#C2410C", linewidth=1.8, label="Sid2 (Right)")
	ax.axhline(threshold, color="#94a3b8", linestyle="--", linewidth=1.0, label=f"Threshold ({threshold})")

	ax.set_ylabel("Noise", fontsize=9)
	ax.tick_params(labelsize=8)
	ax.grid(True, color="#e2e8f0", linewidth=0.7)
	for spine in ("top", "right"):
		ax.spines[spine].set_visible(False)
	ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.18))
	ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
	fig.autofmt_xdate(rotation=0, ha="center")
	fig.tight_layout()
	return _fig_to_png(fig)


def _single_trend_png(history_df: pd.DataFrame, threshold: int, col: str, color: str, title: str) -> bytes | None:
	if history_df is None or history_df.empty:
		return None

	fig, ax = plt.subplots(figsize=(3.6, 2.5), dpi=150)
	ax.plot(history_df["time"], history_df[col], color=color, linewidth=1.6)
	ax.fill_between(history_df["time"], history_df[col], color=color, alpha=0.12)
	ax.axhline(threshold, color="#94a3b8", linestyle="--", linewidth=1.0)

	ax.set_title(title, fontsize=10, color="#1f2937", fontweight="bold", pad=6)
	ax.set_ylabel("Noise", fontsize=8)
	ax.tick_params(labelsize=7)
	ax.grid(True, color="#e2e8f0", linewidth=0.7)
	for spine in ("top", "right"):
		ax.spines[spine].set_visible(False)
	ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
	fig.autofmt_xdate(rotation=0, ha="center")
	fig.tight_layout()
	return _fig_to_png(fig)


def _build_tips(history_df: pd.DataFrame, insights: dict, windows_df: pd.DataFrame, threshold: int) -> list[str]:
	tips: list[str] = []
	if history_df is None or history_df.empty:
		return ["No history was available for this period, so no observations could be derived."]

	avg1 = insights.get("avg_sid1", 0)
	avg2 = insights.get("avg_sid2", 0)
	ev1 = insights.get("events_sid1", 0)
	ev2 = insights.get("events_sid2", 0)
	dominant = insights.get("dominant_side", "Balanced")

	total_events = ev1 + ev2
	if total_events == 0:
		tips.append("The classroom stayed below the noise threshold for the whole window &mdash; discipline was well maintained.")
	else:
		tips.append(
			f"{total_events} readings crossed the threshold ({threshold}): "
			f"{ev1} on the left (Sid1) and {ev2} on the right (Sid2)."
		)

	if dominant and dominant != "Balanced":
		tips.append(f"On average, the {dominant.lower()} was the noisier zone (avg Sid1 {avg1:.0f} vs Sid2 {avg2:.0f}).")
	elif dominant == "Balanced":
		tips.append("Noise was evenly distributed between the left and right zones.")

	if windows_df is not None and not windows_df.empty:
		total_min = float(windows_df["duration_min"].sum())
		peak = int(windows_df["peak_noise"].max())
		longest = windows_df.sort_values("duration_min", ascending=False).iloc[0]
		longest_start = pd.to_datetime(longest["start_time"]).strftime("%H:%M")
		tips.append(
			f"{len(windows_df)} discipline-loss window(s) totalling {total_min:.1f} min were detected; "
			f"peak noise reached {peak}."
		)
		tips.append(
			f"The longest disruption began around {longest_start} "
			f"({longest['duration_min']:.1f} min, dominant zone: {longest['dominant_zone']})."
		)
		tips.append("Recommendation: review activity during the flagged windows and seat noisier groups away from the dominant zone.")
	else:
		tips.append("No sustained disruption windows were detected during this period.")

	return tips


def _kv_table(rows: list[tuple[str, str]]) -> Table:
	table = Table([[k, v] for k, v in rows], colWidths=[6.5 * cm, 9.5 * cm])
	table.setStyle(
		TableStyle(
			[
				("FONTSIZE", (0, 0), (-1, -1), 10),
				("TEXTCOLOR", (0, 0), (0, -1), MUTED),
				("TEXTCOLOR", (1, 0), (1, -1), SLATE),
				("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
				("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
				("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
				("TOPPADDING", (0, 0), (-1, -1), 6),
				("BOTTOMPADDING", (0, 0), (-1, -1), 6),
				("LEFTPADDING", (0, 0), (-1, -1), 8),
			]
		)
	)
	return table


def _windows_table(windows_df: pd.DataFrame) -> Table:
	header = ["Start", "End", "Duration (min)", "Peak noise", "Dominant zone"]
	data = [header]
	for row in windows_df.itertuples(index=False):
		start = pd.to_datetime(row.start_time).strftime("%Y-%m-%d %H:%M")
		end = pd.to_datetime(row.end_time).strftime("%H:%M")
		data.append([start, end, f"{row.duration_min:.2f}", str(int(row.peak_noise)), str(row.dominant_zone)])

	table = Table(data, colWidths=[4.0 * cm, 2.3 * cm, 3.0 * cm, 2.7 * cm, 4.0 * cm], repeatRows=1)
	table.setStyle(
		TableStyle(
			[
				("BACKGROUND", (0, 0), (-1, 0), BLUE),
				("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
				("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
				("FONTSIZE", (0, 0), (-1, -1), 9),
				("TEXTCOLOR", (0, 1), (-1, -1), SLATE),
				("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
				("GRID", (0, 0), (-1, -1), 0.4, BORDER),
				("TOPPADDING", (0, 0), (-1, -1), 5),
				("BOTTOMPADDING", (0, 0), (-1, -1), 5),
				("ALIGN", (1, 0), (-1, -1), "CENTER"),
			]
		)
	)
	return table


def _render_session(story: list, s: dict, sess: dict, threshold: int) -> None:
	start = sess["start_time"]
	end = sess["end_time"]
	duration = end - start
	d_min, d_sec = divmod(int(duration.total_seconds()), 60)
	df = sess["df"]
	insights = sess.get("insights", {})
	windows_df = sess.get("windows_df")
	discipline_pct = sess.get("discipline_pct", 0.0)

	story.append(PageBreak())
	story.append(Paragraph(sess["name"], s["title"]))
	story.append(
		Paragraph(
			f"{start.strftime('%Y-%m-%d %H:%M:%S')} &ndash; {end.strftime('%H:%M:%S')} "
			f"({d_min}m {d_sec}s)",
			s["subtitle"],
		)
	)
	story.append(Spacer(1, 0.25 * cm))

	disturbed_pct = max(0.0, 100.0 - discipline_pct)
	story.append(Paragraph("Session Summary", s["section"]))
	story.append(
		_kv_table(
			[
				("Duration", f"{d_min}m {d_sec}s"),
				("Readings captured", str(len(df))),
				("Time within discipline", f"{discipline_pct:.0f}% (noisy {disturbed_pct:.0f}%)"),
				("Average Sid1 (Left)", f"{insights.get('avg_sid1', 0):.0f}"),
				("Average Sid2 (Right)", f"{insights.get('avg_sid2', 0):.0f}"),
				("Dominant side", str(insights.get("dominant_side", "No data"))),
			]
		)
	)

	combined = _trend_png(df, threshold)
	if combined:
		story.append(Paragraph("Session Trend &ndash; Combined", s["section"]))
		story.append(Image(io.BytesIO(combined), width=16 * cm, height=6.6 * cm))

	sid1_png = _single_trend_png(df, threshold, "sid1", "#1D4ED8", "Sid1 (Left)")
	sid2_png = _single_trend_png(df, threshold, "sid2", "#C2410C", "Sid2 (Right)")
	if sid1_png and sid2_png:
		story.append(Paragraph("Session Trend &ndash; Per Zone", s["section"]))
		side_by_side = Table(
			[[
				Image(io.BytesIO(sid1_png), width=7.8 * cm, height=5.4 * cm),
				Image(io.BytesIO(sid2_png), width=7.8 * cm, height=5.4 * cm),
			]],
			colWidths=[8 * cm, 8 * cm],
		)
		side_by_side.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
		story.append(side_by_side)

	tips = _build_tips(df, insights, windows_df, threshold)
	if tips:
		story.append(Paragraph("Observations", s["section"]))
		for tip in tips:
			story.append(Paragraph(f"&bull;&nbsp; {tip}", s["body"]))
			story.append(Spacer(1, 0.12 * cm))

	story.append(Paragraph("Discipline-Loss Windows", s["section"]))
	if windows_df is None or windows_df.empty:
		story.append(Paragraph("No discipline-loss windows detected during this session.", s["body"]))
	else:
		story.append(_windows_table(windows_df))


def build_pdf_report(
	*,
	generated_at: datetime,
	threshold: int,
	current_sid1: int,
	current_sid2: int,
	status_text: str,
	history_df: pd.DataFrame,
	insights: dict,
	windows_df: pd.DataFrame,
	sessions: list | None = None,
) -> bytes:
	buf = io.BytesIO()
	doc = SimpleDocTemplate(
		buf,
		pagesize=A4,
		title=REPORT_TITLE,
		author="Smart Classroom Monitor",
		topMargin=1.6 * cm,
		bottomMargin=1.6 * cm,
		leftMargin=1.8 * cm,
		rightMargin=1.8 * cm,
	)
	s = _styles()
	story = []

	story.append(Paragraph(REPORT_TITLE, s["title"]))
	story.append(Paragraph("Live camera localization with ThingSpeak-backed noise analytics", s["subtitle"]))
	story.append(Paragraph(f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}", s["subtitle"]))
	story.append(Spacer(1, 0.3 * cm))

	story.append(Paragraph("Current Snapshot", s["section"]))
	story.append(
		_kv_table(
			[
				("Sid1 (Left)", str(current_sid1)),
				("Sid2 (Right)", str(current_sid2)),
				("Difference", str(abs(current_sid1 - current_sid2))),
				("Noise threshold", str(threshold)),
				("Live status", status_text),
			]
		)
	)

	story.append(Paragraph("12-Hour Summary", s["section"]))
	story.append(
		_kv_table(
			[
				("Average Sid1 (Left)", f"{insights.get('avg_sid1', 0):.0f}"),
				("Average Sid2 (Right)", f"{insights.get('avg_sid2', 0):.0f}"),
				("Events above threshold (Left)", str(insights.get("events_sid1", 0))),
				("Events above threshold (Right)", str(insights.get("events_sid2", 0))),
				("Dominant side", str(insights.get("dominant_side", "No data"))),
			]
		)
	)

	chart_png = _trend_png(history_df, threshold)
	if chart_png:
		story.append(Paragraph("Noise Trend &ndash; Combined (last 12 hours)", s["section"]))
		story.append(Image(io.BytesIO(chart_png), width=16 * cm, height=6.6 * cm))

	sid1_png = _single_trend_png(history_df, threshold, "sid1", "#1D4ED8", "Sid1 (Left)")
	sid2_png = _single_trend_png(history_df, threshold, "sid2", "#C2410C", "Sid2 (Right)")
	if sid1_png and sid2_png:
		story.append(Paragraph("Noise Trend &ndash; Per Zone", s["section"]))
		side_by_side = Table(
			[[
				Image(io.BytesIO(sid1_png), width=7.8 * cm, height=5.4 * cm),
				Image(io.BytesIO(sid2_png), width=7.8 * cm, height=5.4 * cm),
			]],
			colWidths=[8 * cm, 8 * cm],
		)
		side_by_side.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
		story.append(side_by_side)

	tips = _build_tips(history_df, insights, windows_df, threshold)
	if tips:
		story.append(Paragraph("Key Observations &amp; Recommendations", s["section"]))
		for tip in tips:
			story.append(Paragraph(f"&bull;&nbsp; {tip}", s["body"]))
			story.append(Spacer(1, 0.12 * cm))

	story.append(Paragraph("Discipline-Loss Windows", s["section"]))
	if windows_df is None or windows_df.empty:
		story.append(Paragraph("No discipline-loss windows detected in the selected range.", s["body"]))
	else:
		story.append(_windows_table(windows_df))

	if sessions:
		story.append(Spacer(1, 0.3 * cm))
		story.append(
			Paragraph(
				f"This report includes {len(sessions)} recorded class session(s); each is detailed on its own page.",
				s["body"],
			)
		)
		for sess in sessions:
			_render_session(story, s, sess, threshold)

	story.append(Spacer(1, 0.8 * cm))
	story.append(Paragraph(f"{REPORT_TITLE} &mdash; automated report", s["footer"]))

	doc.build(story)
	buf.seek(0)
	return buf.getvalue()
