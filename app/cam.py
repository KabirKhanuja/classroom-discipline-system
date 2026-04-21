import os
import time

import cv2
import requests


def _load_local_env() -> None:
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _get_env(primary: str, fallback: str = "") -> str:
    value = os.getenv(primary, "").strip()
    if value:
        return value
    if fallback:
        return os.getenv(fallback, "").strip()
    return ""


def get_thingspeak_config() -> tuple[str, str, int]:
    _load_local_env()
    channel_id = _get_env("THINGSPEAK_CHANNEL_ID", "CHANNEL_ID")
    read_api = _get_env("THINGSPEAK_READ_API_KEY", "READ_API")
    threshold_str = _get_env("NOISE_THRESHOLD") or "2000"
    threshold = int(threshold_str)
    return channel_id, read_api, threshold


def get_last_feed_url(channel_id: str, read_api: str) -> str:
    return (
        f"https://api.thingspeak.com/channels/{channel_id}/feeds/last.json"
        f"?api_key={read_api}"
    )


def _parse_field_value(value):
    if value is None or value == "":
        return None
    return int(float(value))


def _build_recent_feeds_url(last_feed_url: str, results: int = 10) -> str:
    return last_feed_url.replace("/feeds/last.json", "/feeds.json") + f"&results={results}"


def fetch_latest_noise(session: requests.Session, url: str, timeout: int = 5) -> tuple[int, int]:
    data = session.get(url, timeout=timeout).json()
    sid1 = _parse_field_value(data.get("field1"))
    sid2 = _parse_field_value(data.get("field2"))

    # Two nodes often update field1/field2 at different moments, so one field can
    # be null in the very latest feed. Backfill from a few recent records.
    if sid1 is None or sid2 is None:
        recent_url = _build_recent_feeds_url(url, results=12)
        recent = session.get(recent_url, timeout=timeout).json().get("feeds", [])
        for feed in reversed(recent):
            if sid1 is None:
                sid1 = _parse_field_value(feed.get("field1"))
            if sid2 is None:
                sid2 = _parse_field_value(feed.get("field2"))
            if sid1 is not None and sid2 is not None:
                break

    if sid1 is None or sid2 is None:
        raise ValueError("ThingSpeak returned insufficient data for field1/field2")

    return sid1, sid2


def annotate_noise_zones(frame, sid1: int, sid2: int, threshold: int):
    annotated = cv2.flip(frame, 1)
    height, width = annotated.shape[:2]

    if sid1 > threshold:
        cv2.rectangle(annotated, (0, 0), (width // 2, height), (0, 0, 255), 4)
        cv2.putText(
            annotated,
            "NOISE LEFT",
            (30, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )

    if sid2 > threshold:
        cv2.rectangle(annotated, (width // 2, 0), (width, height), (0, 0, 255), 4)
        cv2.putText(
            annotated,
            "NOISE RIGHT",
            (width // 2 + 20, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )

    cv2.putText(
        annotated,
        f"Sid1: {sid1}  Sid2: {sid2}  Threshold: {threshold}",
        (20, height - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )
    return annotated


def run_camera_monitor() -> None:
    channel_id, read_api, threshold = get_thingspeak_config()
    if not channel_id or not read_api:
        raise SystemExit(
            "Missing ThingSpeak credentials. Set THINGSPEAK_CHANNEL_ID/CHANNEL_ID and "
            "THINGSPEAK_READ_API_KEY/READ_API environment variables."
        )

    url = get_last_feed_url(channel_id, read_api)
    session = requests.Session()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        raise SystemExit("Unable to open webcam. Check camera permissions or device index.")

    sid1 = 0
    sid2 = 0
    last_fetch = 0.0

    while True:
        if time.time() - last_fetch > 5:
            try:
                sid1, sid2 = fetch_latest_noise(session, url)
                print("Sid1:", sid1, "Sid2:", sid2)
                last_fetch = time.time()
            except (requests.RequestException, ValueError, TypeError, KeyError):
                pass

        ret, frame = cap.read()
        if not ret:
            continue

        annotated = annotate_noise_zones(frame, sid1, sid2, threshold)
        cv2.imshow("Smart Classroom Monitor", annotated)

        if cv2.waitKey(1) == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_camera_monitor()