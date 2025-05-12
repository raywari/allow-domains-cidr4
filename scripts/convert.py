#!/usr/bin/python3.10

import tldextract
import re
from pathlib import Path
import json
import os
import subprocess

# Пути к файлам
domains_file = 'domains.lst'  # В корне
subnets_file = 'categories/CIDR4/summary.lst'  # Подсети
output_srs = 'domains-cidr4.srs'  # Итоговый файл в корне

def domains_from_file(filepath):
    domains = []
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line in file:
                domain = line.strip()
                if domain and tldextract.extract(domain).suffix:
                    if re.search(r'[^а-я\-]', tldextract.extract(domain).domain):
                        domains.append(tldextract.extract(domain).fqdn)
                    elif not tldextract.extract(domain).domain:
                        domains.append("." + tldextract.extract(domain).suffix)
    except FileNotFoundError:
        print(f"File not found: {filepath}")
    return sorted(set(domains))

def subnets_from_file(filepath):
    subnets = []
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line in file:
                subnet = line.strip()
                if subnet:
                    subnets.append(subnet)
    except FileNotFoundError:
        print(f"File not found: {filepath}")
    return sorted(set(subnets))

def generate_srs_combined(domains, subnets, output_json_directory='JSON', compiled_output_directory='.'):
    os.makedirs(output_json_directory, exist_ok=True)

    data = {
        "version": 3,
        "rules": [
            {
                "domain_suffix": domains,
                "ip_cidr": subnets
            }
        ]
    }

    json_file_path = os.path.join(output_json_directory, "combined.json")
    srs_file_path = os.path.join(compiled_output_directory, output_srs)

    try:
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, indent=4)
        print(f"JSON file generated: {json_file_path}")

        subprocess.run(
            ["sing-box", "rule-set", "compile", json_file_path, "-o", srs_file_path], check=True
        )
        print(f"Compiled .srs file: {srs_file_path}")
    except subprocess.CalledProcessError as e:
        print(f"Compile error {json_file_path}: {e}")
    except Exception as e:
        print(f"Error while processing: {e}")

if __name__ == '__main__':
    domains = domains_from_file(domains_file)
    subnets = subnets_from_file(subnets_file)
    generate_srs_combined(domains, subnets)
