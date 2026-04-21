import cv2
import os
import requests
import time

CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID")
READ_API = os.getenv("THINGSPEAK_READ_API_KEY")

if not CHANNEL_ID or not READ_API:
    raise SystemExit(
        "Missing ThingSpeak credentials. Set THINGSPEAK_CHANNEL_ID and "
        "THINGSPEAK_READ_API_KEY environment variables."
    )

url = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds/last.json?api_key={READ_API}"

cap = cv2.VideoCapture(0)

sid1 = 0
sid2 = 0
last_fetch = 0

while True:

    # fetch every 5 sec
    if time.time() - last_fetch > 5:
        try:
            data = requests.get(url, timeout=5).json()
            sid1 = int(float(data["field1"]))
            sid2 = int(float(data["field2"]))
            print("Sid1:", sid1, "Sid2:", sid2)
            last_fetch = time.time()
        except (requests.RequestException, ValueError, TypeError, KeyError):
            pass

    ret, frame = cap.read()
    frame = cv2.flip(frame,1)

    h,w,_ = frame.shape

    # left side noisy
    if sid1 > 2000:
        cv2.rectangle(frame,(0,0),(w//2,h),(0,0,255),5)
        cv2.putText(frame,"NOISE LEFT",(50,50),
                    cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)

    # right side noisy
    if sid2 > 2000:
        cv2.rectangle(frame,(w//2,0),(w,h),(0,0,255),5)
        cv2.putText(frame,"NOISE RIGHT",(w//2+30,50),
                    cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)

    cv2.imshow("Smart Classroom Monitor", frame)

    if cv2.waitKey(1)==27:
        break

cap.release()
cv2.destroyAllWindows()