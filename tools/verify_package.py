#!/usr/bin/env python3
"""Independently verify a built Immich TOS Docker package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - user-facing dependency message
    raise SystemExit("verify_package: install PyYAML with `python -m pip install -r tools/requirements.txt`") from exc


APP_ID = "le3gold-immich"
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
LANG_KEYS = ("name", "auth", "descript", "release_note", "important")
EXPECTED_FILES = {"config.ini", f"{APP_ID}.lang", f"{APP_ID}.svg", "docker-compose.yml"}
EXPECTED_SERVICES = {"config-init", "immich-server", "immich-machine-learning", "redis", "database"}
EXPECTED_IMAGES = {
    "config-init": "docker.io/busybox:1.37.0",
    "immich-server": "docker.io/altran1502/immich-server:v3.3.4",
    "immich-machine-learning": "docker.io/altran1502/immich-machine-learning:v3.3.4",
    "redis": "docker.io/valkey/valkey:9.1.2",
    "database": "docker.io/pgvector/pgvector:0.8.7-pg14",
}


def fail(message: str) -> None:
    raise SystemExit(f"verify_package: {message}")


def read_member(tar: tarfile.TarFile, name: str) -> bytes:
    member = tar.getmember(name)
    stream = tar.extractfile(member)
    if stream is None:
        fail(f"{name} is not a regular file")
    data = stream.read()
    if b"\r" in data:
        fail(f"{name} contains CR; use LF line endings")
    return data


def text_member(tar: tarfile.TarFile, name: str) -> str:
    try:
        return read_member(tar, name).decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(f"{name} is not UTF-8: {exc}")


def check_config(config_text: str) -> None:
    try:
        config = json.loads(config_text)
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
    if config["id"] != APP_ID:
        fail(f"config.ini id is {config['id']!r}, expected {APP_ID!r}")
    if config["icon"] != f"/images/icons/{APP_ID}.svg":
        fail("config.ini icon path is wrong")
    if config["path"] != "http://${ip}:2283":
        fail("config.ini path must use http://${ip}:2283")
    if config["version"] != "3.3.4":
        fail("config.ini version must be 3.3.4 for this release")
    if config["application_type"] != "docker":
        fail("config.ini application_type must be docker")
    if config["open_path"] is not True:
        fail("config.ini open_path must be true")
    if config["platform"] != "x86_64":
        fail("config.ini platform must be x86_64")
    if config["compose_project"] != APP_ID:
        fail("config.ini compose_project must match the app id")
    if config["user"] != APP_ID:
        fail("config.ini user must match the app id")
    if config["all_user_display"] is not False:
        fail("config.ini all_user_display must be false")
    if config["category"] != ["Phtography_Video"]:
        fail("config.ini category must be the TOS 7.1 enum Phtography_Video")
    if "DockerEngine" not in config["depend"]:
        fail("config.ini depend must include DockerEngine")
    if "docker" not in config["relation"] or "DockerEngine" not in config["relation"]:
        fail("config.ini relation must include docker and DockerEngine")
    for key in ("official", "help"):
        if not str(config[key]).startswith("https://"):
            fail(f"config.ini {key} must be a public https URL")


def check_lang(text: str) -> None:
    sections: list[str] = []
    values: dict[str, dict[str, str]] = {}
    current: str | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"\[([a-z]{2}-[a-z]{2})\]", line)
        if match:
            current = match.group(1)
            if current in values:
                fail(f"{APP_ID}.lang:{number}: duplicate section")
            sections.append(current)
            values[current] = {}
            continue
        if current is None or "=" not in line:
            fail(f"{APP_ID}.lang:{number}: expected a language section or key = value")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not (value.startswith('"') and value.endswith('"') and len(value) >= 2):
            fail(f"{APP_ID}.lang:{number}: {key} is not a double-quoted string")
        if key not in LANG_KEYS:
            fail(f"{APP_ID}.lang:{number}: unknown key {key}")
        values[current][key] = value[1:-1]
    if tuple(sections) != LANGUAGES:
        fail(f"language sections are {sections}, expected the 14 TOS languages")
    for language in LANGUAGES:
        for key in LANG_KEYS:
            if not values[language].get(key):
                fail(f"language [{language}] has an empty {key}")


def check_svg(text: str) -> None:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        fail(f"{APP_ID}.svg is not valid XML: {exc}")
    if root.tag.rsplit("}", 1)[-1] != "svg":
        fail("icon root element is not svg")
    if not root.attrib.get("viewBox"):
        fail("icon SVG must have a viewBox")
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] in {"script", "foreignObject"}:
            fail("icon SVG must not contain script or foreignObject")


def as_env(service: dict) -> dict[str, str]:
    env = service.get("environment", [])
    if isinstance(env, dict):
        return {str(key): str(value) for key, value in env.items()}
    result: dict[str, str] = {}
    for item in env:
        key, _, value = str(item).partition("=")
        result[key] = value
    return result


def check_compose(text: str) -> None:
    try:
        compose = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        fail(f"docker-compose.yml is not valid YAML: {exc}")
    services = compose.get("services")
    if not isinstance(services, dict) or set(services) != EXPECTED_SERVICES:
        fail(f"compose services are {sorted(services or {})}, expected {sorted(EXPECTED_SERVICES)}")
    names: set[str] = set()
    for name, service in services.items():
        image = service.get("image")
        if image != EXPECTED_IMAGES[name]:
            fail(f"{name} image is {image!r}, expected {EXPECTED_IMAGES[name]!r}")
        if "@" not in image and image.rsplit(":", 1)[-1] == "latest":
            fail(f"{name} uses :latest")
        if service.get("user") != "1000:1000":
            fail(f"{name} must run as 1000:1000")
        if service.get("restart") != "unless-stopped":
            fail(f"{name} must use restart: unless-stopped")
        if service.get("privileged"):
            fail(f"{name} must not be privileged")
        if service.get("network_mode") == "host":
            fail(f"{name} must not use host networking")
        security = service.get("security_opt", [])
        if "no-new-privileges:true" not in security:
            fail(f"{name} must set no-new-privileges:true")
        health = service.get("healthcheck")
        if not isinstance(health, dict) or not health.get("test"):
            fail(f"{name} must define a healthcheck")
        container_name = service.get("container_name")
        if not container_name or container_name in names:
            fail(f"{name} has a missing or duplicate container_name")
        names.add(container_name)
        for volume in service.get("volumes", []):
            source = str(volume).split(":", 1)[0]
            if not source.startswith("./") or "/Volume" in source:
                fail(f"{name} must use a relative ./ mount, got {source}")

    if services["immich-server"].get("container_name") != APP_ID:
        fail("immich-server container_name must equal the application id")

    server = services["immich-server"]
    if "2283:2283" not in [str(port) for port in server.get("ports", [])]:
        fail("immich-server must publish 2283:2283")
    for name in ("immich-machine-learning", "redis", "database", "config-init"):
        if services[name].get("ports"):
            fail(f"{name} must not publish a host port")

    dependencies = server.get("depends_on", {})
    for required in ("config-init", "immich-machine-learning", "database", "redis"):
        if required not in dependencies:
            fail(f"immich-server must depend on {required}")
    for required in ("config-init", "immich-machine-learning", "database", "redis"):
        if dependencies[required].get("condition") != "service_healthy":
            fail(f"immich-server dependency {required} must use service_healthy")
    for name in ("immich-machine-learning", "redis", "database"):
        dependency = services[name].get("depends_on", {}).get("config-init", {})
        if dependency.get("condition") != "service_healthy":
            fail(f"{name} must wait for config-init to become healthy")

    env = as_env(server)
    if env.get("DB_PASSWORD_FILE") != "/run/secrets/db-password":
        fail("immich-server must use DB_PASSWORD_FILE")
    if env.get("DB_HOSTNAME") != "database" or env.get("REDIS_HOSTNAME") != "redis":
        fail("immich-server must use Docker DNS service names")
    db_env = as_env(services["database"])
    if db_env.get("POSTGRES_PASSWORD_FILE") != "/run/secrets/db-password":
        fail("database must use POSTGRES_PASSWORD_FILE")
    ml_env = as_env(services["immich-machine-learning"])
    if ml_env.get("HF_ENDPOINT") != "https://hf-mirror.com" or ml_env.get("HF_HUB_DISABLE_XET") != "1":
        fail("machine-learning must use the documented model mirror settings")

    init = services["config-init"]
    init_command = "\n".join(init.get("command", [])) if isinstance(init.get("command"), list) else str(init.get("command", ""))
    for required in ("127.0.0.11", "db-password", "base64", "tr -dc"):
        if required not in init_command:
            fail(f"config-init command is missing {required}")
    for name in ("immich-server", "immich-machine-learning", "redis", "database"):
        mounts = [str(volume) for volume in services[name].get("volumes", [])]
        if not any("./network/hosts:/etc/hosts:ro" in mount for mount in mounts):
            fail(f"{name} must mount the readable hosts file")
        if not any("./network/resolv.conf:/etc/resolv.conf:ro" in mount for mount in mounts):
            fail(f"{name} must mount the readable resolv.conf")
    for name in ("immich-server", "database"):
        mounts = [str(volume) for volume in services[name].get("volumes", [])]
        if not any("./network/db-password:/run/secrets/db-password:ro" in mount for mount in mounts):
            fail(f"{name} must mount db-password read-only")

    meta = compose.get("x-app-meta", {}).get("web", {})
    if meta.get("port") != 2283 or meta.get("protocol") != "http":
        fail("x-app-meta.web must be port 2283 and protocol http")
    if "le3gold-immich-test" in text or "12283" in text:
        fail("production compose contains test-only names or ports")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    if not package.is_file():
        fail(f"package not found: {package}")
    try:
        with tarfile.open(package, "r:gz") as tar:
            members = tar.getmembers()
            names = [member.name for member in members]
            if set(names) != EXPECTED_FILES or len(names) != len(EXPECTED_FILES):
                fail(f"archive root files are {names}, expected exactly {sorted(EXPECTED_FILES)}")
            for member in members:
                if not member.isfile() or member.name.startswith("/") or "/" in member.name:
                    fail(f"archive member is not a flat regular file: {member.name}")
                if member.mode != 0o644:
                    fail(f"{member.name} mode is {oct(member.mode)}, expected 0o644")
                if member.uid != 0 or member.gid != 0:
                    fail(f"{member.name} must have uid/gid 0")
            config_text = text_member(tar, "config.ini")
            lang_text = text_member(tar, f"{APP_ID}.lang")
            svg_text = text_member(tar, f"{APP_ID}.svg")
            compose_text = text_member(tar, "docker-compose.yml")
    except tarfile.TarError as exc:
        fail(f"cannot read archive: {exc}")

    check_config(config_text)
    check_lang(lang_text)
    check_svg(svg_text)
    check_compose(compose_text)

    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    sidecar = package.with_name(package.name + ".sha256")
    if sidecar.is_file():
        expected = sidecar.read_text(encoding="ascii").split()[0]
        if expected != digest:
            fail(f"sha256 mismatch: sidecar {expected}, package {digest}")
    print(f"verified {package}")
    print(f"sha256 {digest}")
    print(f"files {', '.join(sorted(EXPECTED_FILES))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
