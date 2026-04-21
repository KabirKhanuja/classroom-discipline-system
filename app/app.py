import threading
import time
from dataclasses import dataclass
import importlib

import cv2
import pandas as pd
import requests
import streamlit as st

try:
	av = importlib.import_module("av")
	streamlit_webrtc = importlib.import_module("streamlit_webrtc")
	WebRtcMode = streamlit_webrtc.WebRtcMode
	webrtc_streamer = streamlit_webrtc.webrtc_streamer
	WEBRTC_AVAILABLE = True
except ModuleNotFoundError:
	WEBRTC_AVAILABLE = False

from cam import annotate_noise_zones, fetch_latest_noise, get_last_feed_url, get_thingspeak_config


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


st.set_page_config(page_title="Smart Classroom Monitor", page_icon="", layout="wide")

st.title("Smart Classroom Discipline Monitoring")
st.caption("Live camera localization with ThingSpeak-backed classroom noise analytics")

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
		img = frame.to_ndarray(format="bgr24")
		annotated = annotate_noise_zones(img, snap.sid1, snap.sid2, threshold)
		return av.VideoFrame.from_ndarray(annotated, format="bgr24")


st.subheader("Live Camera View")
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
		"Install app/requirements.txt to enable it."
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

col1, col2, col3, col4 = st.columns(4)
col1.metric("Sid1 (Left)", current.sid1)
col2.metric("Sid2 (Right)", current.sid2)
col3.metric("Difference", abs(current.sid1 - current.sid2))
col4.metric("Live Status", status_text)

if current.last_error:
	st.warning(f"Latest ThingSpeak fetch warning: {current.last_error}")

st.subheader("ThingSpeak Trends")
try:
	history_df = fetch_history(channel_id, read_api, history_points)
except requests.RequestException as exc:
	st.error(f"Unable to fetch ThingSpeak history: {exc}")
	history_df = pd.DataFrame(columns=["time", "sid1", "sid2"])

if history_df.empty:
	st.info("No valid history available yet. Check whether field1 and field2 are being uploaded.")
else:
	plot_df = history_df.set_index("time")[["sid1", "sid2"]]
	st.line_chart(plot_df, use_container_width=True)

	insights = compute_insights(history_df, threshold)
	a1, a2, a3 = st.columns(3)
	a1.metric("Average Sid1", f"{insights['avg_sid1']:.1f}")
	a2.metric("Average Sid2", f"{insights['avg_sid2']:.1f}")
	a3.metric("Dominant Disturbance Zone", insights["dominant_side"])

	b1, b2 = st.columns(2)
	b1.metric(f"Sid1 events > {threshold}", insights["events_sid1"])
	b2.metric(f"Sid2 events > {threshold}", insights["events_sid2"])

	st.subheader("Recent Samples")
	st.dataframe(
		history_df.sort_values("time", ascending=False).head(15),
		use_container_width=True,
		hide_index=True,
	)

if auto_refresh:
	time.sleep(refresh_sec)
	st.rerun()
