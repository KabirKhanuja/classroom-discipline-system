import importlib
import threading
import time
from dataclasses import dataclass

import cv2
import pandas as pd
import requests
import streamlit as st

from cam import annotate_noise_zones, fetch_latest_noise, get_last_feed_url, get_thingspeak_config

try:
	av = importlib.import_module("av")
	streamlit_webrtc = importlib.import_module("streamlit_webrtc")
	WebRtcMode = streamlit_webrtc.WebRtcMode
	webrtc_streamer = streamlit_webrtc.webrtc_streamer
	WEBRTC_AVAILABLE = True
except ModuleNotFoundError:
	WEBRTC_AVAILABLE = False


@dataclass
class NoiseSnapshot:
	sid1: int = 0
	sid2: int = 0
	last_update: float = 0.0
	last_error: str = ""


class NoiseCache:
	def __init__(self, url: str, fetch_interval: int = 5):
		self.url = url
		self.fetch_interval = fetch_interval
		self.session = requests.Session()
		self.snapshot = NoiseSnapshot()
		self.lock = threading.Lock()

	def get_snapshot(self) -> NoiseSnapshot:
		with self.lock:
			return NoiseSnapshot(
				sid1=self.snapshot.sid1,
				sid2=self.snapshot.sid2,
				last_update=self.snapshot.last_update,
				last_error=self.snapshot.last_error,
			)

	def update_if_stale(self) -> None:
		now = time.time()
		with self.lock:
			if now - self.snapshot.last_update < self.fetch_interval:
				return

		try:
			sid1, sid2 = fetch_latest_noise(self.session, self.url)
			with self.lock:
				self.snapshot.sid1 = sid1
				self.snapshot.sid2 = sid2
				self.snapshot.last_update = now
				self.snapshot.last_error = ""
		except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
			with self.lock:
				self.snapshot.last_error = str(exc)


def fetch_history(channel_id: str, read_api: str, results: int) -> pd.DataFrame:
	history_url = (
		f"https://api.thingspeak.com/channels/{channel_id}/feeds.json"
		f"?api_key={read_api}&results={results}"
	)
	payload = requests.get(history_url, timeout=10).json()
	feeds = payload.get("feeds", [])

	rows = []
	for item in feeds:
		try:
			rows.append(
				{
					"time": pd.to_datetime(item["created_at"]),
					"sid1": int(float(item["field1"])),
					"sid2": int(float(item["field2"])),
				}
			)
		except (TypeError, ValueError, KeyError):
			continue

	return pd.DataFrame(rows)


def compute_insights(df: pd.DataFrame, threshold: int) -> dict:
	if df.empty:
		return {
			"avg_sid1": 0,
			"avg_sid2": 0,
			"events_sid1": 0,
			"events_sid2": 0,
			"dominant_side": "No data",
		}

	avg_sid1 = float(df["sid1"].mean())
	avg_sid2 = float(df["sid2"].mean())
	events_sid1 = int((df["sid1"] > threshold).sum())
	events_sid2 = int((df["sid2"] > threshold).sum())

	if avg_sid1 > avg_sid2:
		dominant_side = "Left side"
	elif avg_sid2 > avg_sid1:
		dominant_side = "Right side"
	else:
		dominant_side = "Balanced"

	return {
		"avg_sid1": avg_sid1,
		"avg_sid2": avg_sid2,
		"events_sid1": events_sid1,
		"events_sid2": events_sid2,
		"dominant_side": dominant_side,
	}


def detect_discipline_loss_windows(df: pd.DataFrame, threshold: int, max_gap_sec: int = 90) -> pd.DataFrame:
	if df.empty:
		return pd.DataFrame(
			columns=[
				"start_time",
				"end_time",
				"duration_sec",
				"duration_min",
				"peak_noise",
				"dominant_zone",
			]
		)

	work = df.sort_values("time").copy()
	windows = []
	current = None

	def close_window(win):
		duration = max(int((win["end"] - win["start"]).total_seconds()), 0)
		if win["both_count"] >= max(win["left_count"], win["right_count"]):
			dominant_zone = "Both"
		elif win["left_count"] > win["right_count"]:
			dominant_zone = "Left"
		elif win["right_count"] > win["left_count"]:
			dominant_zone = "Right"
		else:
			dominant_zone = "Balanced"

		windows.append(
			{
				"start_time": win["start"],
				"end_time": win["end"],
				"duration_sec": duration,
				"duration_min": round(duration / 60.0, 2),
				"peak_noise": win["peak_noise"],
				"dominant_zone": dominant_zone,
			}
		)

	for row in work.itertuples(index=False):
		timestamp = row.time
		sid1_high = row.sid1 > threshold
		sid2_high = row.sid2 > threshold
		is_noisy = sid1_high or sid2_high

		if not is_noisy:
			if current is not None:
				close_window(current)
				current = None
			continue

		if current is None:
			current = {
				"start": timestamp,
				"end": timestamp,
				"peak_noise": max(int(row.sid1), int(row.sid2)),
				"left_count": 0,
				"right_count": 0,
				"both_count": 0,
			}
		else:
			gap = (timestamp - current["end"]).total_seconds()
			if gap > max_gap_sec:
				close_window(current)
				current = {
					"start": timestamp,
					"end": timestamp,
					"peak_noise": max(int(row.sid1), int(row.sid2)),
					"left_count": 0,
					"right_count": 0,
					"both_count": 0,
				}
			else:
				current["end"] = timestamp
				current["peak_noise"] = max(current["peak_noise"], int(row.sid1), int(row.sid2))

		if sid1_high and sid2_high:
			current["both_count"] += 1
		elif sid1_high:
			current["left_count"] += 1
		elif sid2_high:
			current["right_count"] += 1

	if current is not None:
		close_window(current)

	if not windows:
		return pd.DataFrame(
			columns=[
				"start_time",
				"end_time",
				"duration_sec",
				"duration_min",
				"peak_noise",
				"dominant_zone",
			]
		)

	return pd.DataFrame(windows)


st.set_page_config(page_title="Smart Classroom Monitor", layout="wide")

st.markdown(
	"""
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
	</style>
	""",
	unsafe_allow_html=True,
)

st.title("Smart Classroom Discipline Monitoring")
st.caption("Live camera localization with ThingSpeak-backed noise analytics")

channel_id, read_api, default_threshold = get_thingspeak_config()
if not channel_id or not read_api:
	st.error(
		"Missing ThingSpeak credentials. Set THINGSPEAK_CHANNEL_ID/CHANNEL_ID and "
		"THINGSPEAK_READ_API_KEY/READ_API in environment or app/.env"
	)
	st.stop()

with st.sidebar:
	st.subheader("Controls")
	threshold = st.slider("Noise Threshold", 200, 4095, default_threshold, 50)
	history_points = st.slider("History Points", 20, 500, 120, 20)
	max_gap_sec = st.slider("Window Merge Gap (sec)", 15, 300, 90, 15)
	refresh_sec = st.slider("Dashboard Refresh (sec)", 3, 30, 10, 1)
	auto_refresh = st.toggle("Auto Refresh Analytics", value=True)

last_url = get_last_feed_url(channel_id, read_api)
if "noise_cache" not in st.session_state:
	st.session_state.noise_cache = NoiseCache(last_url, fetch_interval=5)

noise_cache: NoiseCache = st.session_state.noise_cache


class CameraOverlayProcessor:
	def recv(self, frame):
		noise_cache.update_if_stale()
		snap = noise_cache.get_snapshot()
		image = frame.to_ndarray(format="bgr24")
		annotated = annotate_noise_zones(image, snap.sid1, snap.sid2, threshold)
		return av.VideoFrame.from_ndarray(annotated, format="bgr24")


st.subheader("Live Camera View")
st.markdown('<div class="panel">', unsafe_allow_html=True)
if WEBRTC_AVAILABLE:
	webrtc_streamer(
		key="smart-classroom-cam",
		mode=WebRtcMode.SENDRECV,
		media_stream_constraints={"video": True, "audio": False},
		video_processor_factory=CameraOverlayProcessor,
		async_processing=True,
	)
else:
	st.warning(
		"Live embedded camera requires streamlit-webrtc and av. "
		"Install dependencies in app/requirements.txt to enable it."
	)
	if st.button("Show Current Camera Snapshot"):
		cap = cv2.VideoCapture(0)
		ret, frame = cap.read()
		cap.release()
		if ret:
			noise_cache.update_if_stale()
			snap = noise_cache.get_snapshot()
			annotated = annotate_noise_zones(frame, snap.sid1, snap.sid2, threshold)
			st.image(annotated, channels="BGR", use_container_width=True)
		else:
			st.error("Could not capture camera frame.")
st.markdown("</div>", unsafe_allow_html=True)

try:
	noise_cache.update_if_stale()
	current = noise_cache.get_snapshot()
except Exception:
	current = NoiseSnapshot()

status_text = "Normal"
if current.sid1 > threshold and current.sid2 > threshold:
	status_text = "High disturbance on both sides"
elif current.sid1 > threshold:
	status_text = "High disturbance on left side"
elif current.sid2 > threshold:
	status_text = "High disturbance on right side"

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("Sid1 (Left)", current.sid1)
metric2.metric("Sid2 (Right)", current.sid2)
metric3.metric("Difference", abs(current.sid1 - current.sid2))
metric4.metric("Live Status", status_text)

if current.last_error:
	st.warning(f"Latest ThingSpeak fetch warning: {current.last_error}")

st.subheader("ThingSpeak Trends")
try:
	history_df = fetch_history(channel_id, read_api, history_points)
except requests.RequestException as exc:
	st.error(f"Unable to fetch ThingSpeak history: {exc}")
	history_df = pd.DataFrame(columns=["time", "sid1", "sid2"])

if history_df.empty:
	st.info("No valid history available yet. Verify field1 and field2 uploads from ESP32 nodes.")
else:
	plot_df = history_df.set_index("time")[["sid1", "sid2"]]
	st.line_chart(plot_df, use_container_width=True)

	insights = compute_insights(history_df, threshold)
	insight1, insight2, insight3 = st.columns(3)
	insight1.metric("Average Sid1", f"{insights['avg_sid1']:.1f}")
	insight2.metric("Average Sid2", f"{insights['avg_sid2']:.1f}")
	insight3.metric("Dominant Disturbance Zone", insights["dominant_side"])

	event1, event2 = st.columns(2)
	event1.metric(f"Sid1 events > {threshold}", insights["events_sid1"])
	event2.metric(f"Sid2 events > {threshold}", insights["events_sid2"])

	st.subheader("Recent Samples")
	st.dataframe(
		history_df.sort_values("time", ascending=False).head(15),
		use_container_width=True,
		hide_index=True,
	)

	st.subheader("Discipline Loss Windows")
	loss_windows = detect_discipline_loss_windows(history_df, threshold, max_gap_sec=max_gap_sec)
	if loss_windows.empty:
		st.success("No discipline-loss windows found for the selected trend range.")
	else:
		total_loss_min = loss_windows["duration_min"].sum()
		window_count = len(loss_windows)
		c1, c2 = st.columns(2)
		c1.metric("Loss Windows", window_count)
		c2.metric("Total Loss Time (min)", f"{total_loss_min:.2f}")

		for idx, row in loss_windows.iterrows():
			start_txt = row["start_time"].strftime("%H:%M:%S")
			end_txt = row["end_time"].strftime("%H:%M:%S")
			st.write(
				f"{idx + 1}. {start_txt} to {end_txt} | Zone: {row['dominant_zone']} | "
				f"Peak: {int(row['peak_noise'])}"
			)

		display_windows = loss_windows.copy()
		display_windows["start_time"] = display_windows["start_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
		display_windows["end_time"] = display_windows["end_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
		st.dataframe(display_windows, use_container_width=True, hide_index=True)

if auto_refresh:
	time.sleep(refresh_sec)
	st.rerun()
