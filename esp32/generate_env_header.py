#!/usr/bin/env python3
"""Generate env_config.h from esp32/.env for Arduino sketches."""

from pathlib import Path


def parse_env(env_path: Path) -> dict:
    data = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def escape_cpp_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    env_path = base_dir / ".env"
    out_path = base_dir / "env_config.h"

    if not env_path.exists():
        raise SystemExit("Missing esp32/.env file")

    env = parse_env(env_path)
    missing = [k for k in ("ssid", "password", "apiKey") if not env.get(k)]
    if missing:
        raise SystemExit(f"Missing required .env keys: {', '.join(missing)}")

    content = (
        "#ifndef ENV_CONFIG_H\n"
        "#define ENV_CONFIG_H\n\n"
        f"static const char WIFI_SSID[] = \"{escape_cpp_string(env['ssid'])}\";\n"
        f"static const char WIFI_PASSWORD[] = \"{escape_cpp_string(env['password'])}\";\n"
        f"static const char THINGSPEAK_API_KEY[] = \"{escape_cpp_string(env['apiKey'])}\";\n\n"
        "#endif\n"
    )

    out_path.write_text(content, encoding="utf-8")
    print(f"Generated {out_path}")


if __name__ == "__main__":
    main()
