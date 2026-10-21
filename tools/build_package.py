#!/usr/bin/env python3
"""Build a deterministic TOS 7 Docker application archive.

The release archive contains exactly four regular files at its root:

    config.ini
    <appid>.lang
    <appid>.svg
    docker-compose.yml

The gzip and tar metadata are fixed so rebuilding the same inputs produces the
same bytes and the same SHA-256.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
LANG_KEYS = ("name", "auth", "descript", "release_note", "important")
LANGUAGES = (
    "en-us",
    "zh-cn",
    "zh-hk",
    "fr-fr",
    "de-de",
    "it-it",
    "es-es",
    "hu-hu",
    "ja-jp",
    "ko-kr",
    "pl-pl",
    "ru-ru",
    "tr-tr",
    "pt-pt",
)


def fail(message: str) -> None:
    raise SystemExit(f"build_package: {message}")


def read_text(path: Path) -> str:
    if not path.is_file():
        fail(f"missing file: {path.relative_to(ROOT)}")
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        fail(f"{path.relative_to(ROOT)} has a UTF-8 BOM")
    if b"\r" in data:
        fail(f"{path.relative_to(ROOT)} contains CR; use LF line endings")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(f"{path.relative_to(ROOT)} is not UTF-8: {exc}")


def load_config() -> dict:
    try:
        config = json.loads(read_text(ROOT / "config.ini"))
    except json.JSONDecodeError as exc:
        fail(f"config.ini is not valid JSON: {exc}")
    required = {
        "id",
        "icon",
        "publisher",
        "path",
        "exec",
        "open_path",
        "help",
        "version",
        "low_version",
        "category",
        "depend",
        "relation",
        "platform",
        "official",
        "application_type",
        "compose_project",
        "user",
        "all_user_display",
        "allow_open_in_mobile",
    }
    missing = sorted(required - set(config))
    if missing:
        fail(f"config.ini missing fields: {', '.join(missing)}")
    if config["application_type"] != "docker":
        fail("config.ini application_type must be docker")
    if config["open_path"] is not True:
        fail("config.ini open_path must be true for the external web UI")
    if config["platform"] != "x86_64":
        fail("config.ini platform must be x86_64")
    if config["path"] != "http://${ip}:2283":
        fail("config.ini path must use the ${ip} placeholder and port 2283")
    if config["icon"] != f"/images/icons/{config['id']}.svg":
        fail("config.ini icon must be /images/icons/<appid>.svg")
    if "DockerEngine" not in config.get("depend", []):
        fail("config.ini depend must include DockerEngine")
    if "docker" not in config.get("relation", []) or "DockerEngine" not in config.get("relation", []):
        fail("config.ini relation must include docker and DockerEngine")
    if config.get("all_user_display") is not False:
        fail("config.ini all_user_display must be false for per-user access")
    return config


def check_lang(path: Path) -> None:
    text = read_text(path)
    sections: list[str] = []
    fields: dict[str, dict[str, str]] = {}
    current: str | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"\[([a-z]{2}-[a-z]{2})\]", line)
        if match:
            current = match.group(1)
            if current in fields:
                fail(f"{path.name}:{number}: duplicate section [{current}]")
            sections.append(current)
            fields[current] = {}
            continue
        if current is None or "=" not in line:
            fail(f"{path.name}:{number}: expected [language] or key = \"value\"")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not (value.startswith('"') and value.endswith('"') and len(value) >= 2):
            fail(f"{path.name}:{number}: {key} must be a double-quoted string")
        if key not in LANG_KEYS:
            fail(f"{path.name}:{number}: unknown key {key}")
        fields[current][key] = value[1:-1]
    if tuple(sections) != LANGUAGES:
        fail(f"{path.name}: expected {len(LANGUAGES)} language sections in order; got {sections}")
    for language in LANGUAGES:
        for key in LANG_KEYS:
            if not fields[language].get(key):
                fail(f"{path.name}: [{language}] {key} is empty")


def check_compose(path: Path, app_id: str) -> None:
    text = read_text(path)
    prohibited = (
        (r"(?m)^\s*privileged\s*:\s*true\s*$", "privileged: true"),
        (r"(?m)^\s*network_mode\s*:\s*[\"']?host[\"']?\s*$", "network_mode: host"),
        (r"(?m)^\s*-\s*DB_PASSWORD\s*=", "plaintext DB_PASSWORD"),
        (r"(?m)^\s*-\s*POSTGRES_PASSWORD\s*=", "plaintext POSTGRES_PASSWORD"),
        (r"(?m)^\s*image\s*:\s*[^\n]*:latest\s*$", ":latest image tag"),
    )
    for pattern, label in prohibited:
        if re.search(pattern, text):
            fail(f"docker-compose.yml contains prohibited {label}")
    if "2283:2283" not in text:
        fail("docker-compose.yml must publish 2283:2283")
    if "/Volume" in text:
        fail("docker-compose.yml must not hardcode a /Volume* host path")
    if "./network:/config" not in text or "./library:/data" not in text:
        fail("docker-compose.yml must use relative ./ mounts for application data")
    if "x-app-meta:" not in text or "port: 2283" not in text or "protocol: http" not in text:
        fail("docker-compose.yml is missing the x-app-meta web section")
    for required in (
        "config-init",
        "immich-server",
        "immich-machine-learning",
        "redis",
        "database",
        "DB_PASSWORD_FILE",
        "POSTGRES_PASSWORD_FILE",
        "127.0.0.11",
        "HF_ENDPOINT=https://hf-mirror.com",
        "HF_HUB_DISABLE_XET=1",
    ):
        if required not in text:
            fail(f"docker-compose.yml is missing {required}")


def build(config: dict, output: Path) -> None:
    app_id = config["id"]
    lang_name = f"{app_id}.lang"
    svg_name = f"{app_id}.svg"
    icon_source = ROOT / config["icon"].lstrip("/")
    check_lang(ROOT / lang_name)
    check_compose(ROOT / "docker-compose.yml", app_id)
    read_text(icon_source)
    files = {
        "config.ini": read_text(ROOT / "config.ini").encode("utf-8"),
        lang_name: read_text(ROOT / lang_name).encode("utf-8"),
        svg_name: read_text(icon_source).encode("utf-8"),
        "docker-compose.yml": read_text(ROOT / "docker-compose.yml").encode("utf-8"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for name in sorted(files):
                    data = files[name]
                    info = tarfile.TarInfo(name=name)
                    info.size = len(data)
                    info.mtime = 0
                    info.mode = 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    tar.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (output.parent / f"{output.name}.sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
    print(f"built {output} ({output.stat().st_size:,} bytes)")
    print(f"sha256 {digest}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=BUILD / "le3gold-immich.tar.gz")
    args = parser.parse_args()
    config = load_config()
    build(config, args.output.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
