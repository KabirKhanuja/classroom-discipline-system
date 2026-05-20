"""Presentation-only helpers (styling + layout). No data/backend logic here."""

import html

import streamlit as st

GLOBAL_CSS = """
<style>
	:root {
		--app-bg-start: #f7f8fb;
		--app-bg-end: #eef2f7;
		--text-main: #1f2937;
		--text-subtle: #4b5563;
		--panel-bg: #ffffff;
		--panel-border: #d8dee8;
		--panel-shadow: 0 8px 18px rgba(20, 33, 61, 0.05);
		--sidebar-bg: #f8fafc;
		--sidebar-border: #d9e2ec;
		--sidebar-heading: #111827;
		--sidebar-text: #374151;
		--sidebar-muted: #6b7280;
		--accent-blue: #1D4ED8;
		--accent-orange: #C2410C;
		--accent-violet: #7C3AED;
	}

	html[data-theme="dark"] {
		--app-bg-start: #111827;
		--app-bg-end: #0f172a;
		--text-main: #e5e7eb;
		--text-subtle: #cbd5e1;
		--panel-bg: #111827;
		--panel-border: #334155;
		--panel-shadow: 0 10px 22px rgba(0, 0, 0, 0.35);
		--sidebar-bg: #111827;
		--sidebar-border: #374151;
		--sidebar-heading: #f3f4f6;
		--sidebar-text: #e5e7eb;
		--sidebar-muted: #94a3b8;
	}

	.stApp {
		background: linear-gradient(120deg, var(--app-bg-start) 0%, var(--app-bg-end) 100%);
		color: var(--text-main);
	}

	h1, h2, h3, h4, h5, h6, p, span, label, div {
		color: var(--text-main);
	}

	[data-testid="stCaptionContainer"] p,
	[data-testid="stSidebar"] p,
	[data-testid="stSidebar"] label {
		color: var(--text-subtle);
	}

	[data-testid="stSidebar"] {
		background: var(--sidebar-bg);
		border-right: 1px solid var(--sidebar-border);
	}

	[data-testid="stSidebar"] h1,
	[data-testid="stSidebar"] h2,
	[data-testid="stSidebar"] h3 {
		color: var(--sidebar-heading);
		font-weight: 650;
	}

	[data-testid="stSidebar"] p,
	[data-testid="stSidebar"] label,
	[data-testid="stSidebar"] span,
	[data-testid="stSidebar"] div {
		color: var(--sidebar-text);
	}

	[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {
		padding-top: 0.2rem;
		padding-bottom: 0.2rem;
	}

	[data-testid="stSidebar"] .stSlider p,
	[data-testid="stSidebar"] .stToggle label {
		color: var(--sidebar-muted);
	}

	.block-container {
		padding-top: 1.2rem;
		max-width: 1200px;
	}

	.panel {
		padding: 0.9rem 1rem;
		border-radius: 14px;
		border: 1px solid var(--panel-border);
		background: var(--panel-bg);
		box-shadow: var(--panel-shadow);
	}

	/* Page title + section headers */
	h1 {
		font-weight: 750;
		letter-spacing: -0.02em;
	}
	.block-container h2, .block-container h3 {
		font-weight: 680;
		letter-spacing: -0.01em;
		padding-bottom: 0.35rem;
		border-bottom: 1px solid var(--panel-border);
		margin-bottom: 0.6rem;
	}

	/* Metric cards */
	[data-testid="stMetric"] {
		background: var(--panel-bg);
		border: 1px solid var(--panel-border);
		border-radius: 14px;
		padding: 0.85rem 1rem;
		box-shadow: var(--panel-shadow);
		transition: transform 0.12s ease, box-shadow 0.12s ease;
	}
	[data-testid="stMetric"]:hover {
		transform: translateY(-2px);
		box-shadow: 0 12px 24px rgba(20, 33, 61, 0.10);
	}
	[data-testid="stMetricLabel"] p {
		color: var(--text-subtle);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		font-size: 0.72rem;
	}
	[data-testid="stMetricValue"] {
		font-weight: 720;
		color: var(--text-main);
	}
	[data-testid="stMetricValue"] > div {
		white-space: normal;
		overflow: visible;
		line-height: 1.15;
		font-size: clamp(1.1rem, 2vw, 1.9rem);
	}

	/* Per-metric colored accent bar (matches SID1/SID2 chart colors) */
	[data-testid="stColumn"]:nth-of-type(1) [data-testid="stMetric"] {
		border-top: 3px solid var(--accent-blue);
	}
	[data-testid="stColumn"]:nth-of-type(2) [data-testid="stMetric"] {
		border-top: 3px solid var(--accent-orange);
	}
	[data-testid="stColumn"]:nth-of-type(3) [data-testid="stMetric"] {
		border-top: 3px solid var(--accent-violet);
	}

	/* Buttons */
	.stButton > button,
	.stDownloadButton > button {
		border-radius: 10px;
		border: 1px solid var(--panel-border);
		font-weight: 600;
		transition: all 0.12s ease;
	}
	.stButton > button:hover,
	.stDownloadButton > button:hover {
		border-color: var(--accent-blue);
		color: var(--accent-blue);
		transform: translateY(-1px);
		box-shadow: 0 6px 14px rgba(29, 78, 216, 0.15);
	}

	/* Info / warning callouts */
	[data-testid="stAlert"] {
		border-radius: 12px;
	}

	/* History table */
	[data-testid="stDataFrame"] {
		border-radius: 12px;
		overflow: hidden;
		border: 1px solid var(--panel-border);
		box-shadow: var(--panel-shadow);
	}

	/* Full-width live-status banner */
	.status-banner {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		width: 100%;
		margin: 0.4rem 0 0.2rem 0;
		padding: 0.9rem 1.15rem;
		border-radius: 14px;
		border: 1px solid var(--panel-border);
		box-shadow: var(--panel-shadow);
	}
	.status-banner .status-dot {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		flex: 0 0 auto;
		box-shadow: 0 0 0 4px rgba(0, 0, 0, 0.04);
	}
	.status-banner .status-label {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.75;
		margin: 0;
	}
	.status-banner .status-text {
		font-size: 1.25rem;
		font-weight: 720;
		margin: 0;
		line-height: 1.2;
	}
	.status-normal { background: #ecfdf5; border-color: #a7f3d0; }
	.status-normal .status-dot { background: #16a34a; }
	.status-normal .status-text, .status-normal .status-label { color: #065f46; }
	.status-warn { background: #fffbeb; border-color: #fde68a; }
	.status-warn .status-dot { background: #f59e0b; }
	.status-warn .status-text, .status-warn .status-label { color: #92400e; }
	.status-alert { background: #fef2f2; border-color: #fecaca; }
	.status-alert .status-dot { background: #dc2626; }
	.status-alert .status-text, .status-alert .status-label { color: #991b1b; }
</style>
"""


def inject_global_styles() -> None:
	st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_status_banner(status_text: str, severity: str) -> None:
	"""severity: 'normal' | 'warn' | 'alert' (presentation only)."""
	level = severity if severity in {"normal", "warn", "alert"} else "normal"
	safe_text = html.escape(status_text)
	st.markdown(
		f"""
		<div class="status-banner status-{level}">
			<span class="status-dot"></span>
			<div>
				<p class="status-label">Live Status</p>
				<p class="status-text">{safe_text}</p>
			</div>
		</div>
		""",
		unsafe_allow_html=True,
	)
