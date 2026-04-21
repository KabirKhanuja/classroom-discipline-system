Use `.env` for secrets and generate a local header before uploading.

1. Fill `esp32/.env`:
	- `ssid=...`
	- `password=...`
	- `apiKey=...`
2. Generate header:
	- `python3 esp32/generate_env_header.py`
3. Upload `sid1.ino` and `sid2.ino` from `esp32/` as usual in Arduino IDE.

`esp32/env_config.h` is ignored by git so secrets are not committed.


---

## FYI: 

If you don't wanna work around with the .env mess, simply remove that and directly hardcode it in your code for .ino files that will directly work and store on your microcontroller