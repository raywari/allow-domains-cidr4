#!/usr/bin/env python3
import os
import sys
import shutil
import tarfile
import subprocess
from pathlib import Path

import requests

# SETTINGS
SING_BOX_VERSION = os.getenv("SING_BOX_VERSION", "1.11.11")
WORK_DIR = Path(".")
DOWNLOAD_URL = (
    f"https://github.com/SagerNet/sing-box/releases/download/"
    f"v{SING_BOX_VERSION}/sing-box-{SING_BOX_VERSION}-linux-amd64.tar.gz"
)
TARBALL = WORK_DIR / f"sing-box-{SING_BOX_VERSION}-linux-amd64.tar.gz"
EXTRACT_DIR = WORK_DIR / f"sing-box-{SING_BOX_VERSION}-linux-amd64"
CIDR_FILE = Path("categories/CIDR4/summary.lst")
DOMAINS_FILE = Path("domains.lst")
RULES_JSON = WORK_DIR / "rules.json"
OUTPUT_SRS = Path("categories/Rulesets/domains-cidr4.srs")


def download_and_extract():
    print(f"Скачиваем {DOWNLOAD_URL}")
    resp = requests.get(DOWNLOAD_URL, stream=True)
    resp.raise_for_status()
    with open(TARBALL, "wb") as fd:
        for chunk in resp.iter_content(1024 * 1024):
            fd.write(chunk)

    print(f"Распаковываем {TARBALL}")
    with tarfile.open(TARBALL) as tar:
        tar.extractall()

    if not EXTRACT_DIR.exists():
        print("Ошибка распаковки", file=sys.stderr)
        sys.exit(1)


def build_rules_json():
    if not CIDR_FILE.exists() or not DOMAINS_FILE.exists():
        print("Отсутствуют категории/Rulesets/summary.lst или domains.lst", file=sys.stderr)
        sys.exit(1)

    print("Генерируем rules.json")
    with open(DOMAINS_FILE) as f:
        domains = [d.strip() for d in f if d.strip()]
    with open(CIDR_FILE) as f:
        cidrs = [c.strip() for c in f if c.strip()]

    domains = [".ua" if d == "ua" else d for d in domains]

    payload = {
        "version": 3,
        "rules": [
            {
                "domain_suffix": domains,
                "ip_cidr": cidrs
            }
        ]
    }

    import json
    with open(RULES_JSON, "w") as f:
        json.dump(payload, f, indent=2)

def compile_srs():
    bin_path = EXTRACT_DIR / "sing-box"
    if not bin_path.exists():
        print("sing-box бинарь не найден", file=sys.stderr)
        sys.exit(1)

    print("Компилируем SRS правила")
    # sing-box rule-set compile rules.json
    subprocess.run(
        [str(bin_path), "rule-set", "compile", str(RULES_JSON)],
        check=True
    )

    os.makedirs(OUTPUT_SRS.parent, exist_ok=True)
    if Path("rules.srs").exists():
        shutil.move("rules.srs", OUTPUT_SRS)
        print(f"Сгенерирован {OUTPUT_SRS}")
    else:
        print("Файл rules.srs не найден", file=sys.stderr)
        sys.exit(1)


def cleanup():
    for p in [TARBALL, RULES_JSON]:
        if p.exists():
            p.unlink()
    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)


def main():
    download_and_extract()
    build_rules_json()
    compile_srs()
    cleanup()


if __name__ == "__main__":
    main()
