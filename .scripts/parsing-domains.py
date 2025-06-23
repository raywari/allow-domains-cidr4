#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
from urllib.parse import urlparse
try:
    import tomllib
except ImportError:
    import toml as tomllib
try:
    import requests
except ImportError:
    requests = None

V2FLY_REPO_URL = "https://github.com/v2fly/domain-list-community.git"
V2FLY_CLONE_DIR = "tmp/domain-list-community"
V2FLY_DATA_DIR = os.path.join(V2FLY_CLONE_DIR, "data")
CONFIG_PATH = ".scripts/config/parsing-domains.toml"
DOMAINS_FILE = "domains.lst"
CATEGORIES_DIR = "categories/Services"

def generate_from_regex(regex_pattern):
    try:
        regex = regex_pattern.replace('^', '').replace('$', '')
        regex = re.sub(r'\(([^|]+)\|([^)]+)\)', r'(\1|\2)', regex)
        parts = []
        for part in re.split(r'([()|])', regex):
            if not part or part in '()':
                continue
            if part == '|':
                parts.append('|')
            else:
                parts.append(part)
        variants = ['']
        i = 0
        while i < len(parts):
            part = parts[i]
            if part == '|':
                left = variants.pop()
                right = parts[i+1]
                variants.append(f'({left}|{right})')
                i += 2
            else:
                if i+1 < len(parts) and parts[i+1] in ('?', '*', '+', '{'):
                    quant = parts[i+1]
                    if quant == '?':
                        variants = [v + part for v in variants] + variants.copy()
                    elif quant == '*':
                        variants = [v + part*2 for v in variants] + [v + part for v in variants] + variants.copy()
                    elif quant == '+':
                        variants = [v + part for v in variants] + [v + part*2 for v in variants]
                    elif quant.startswith('{'):
                        n = int(re.search(r'\{(\d+)\}', quant).group(1))
                        variants = [v + part*n for v in variants]
                    i += 2
                else:
                    variants = [v + part for v in variants]
                    i += 1
        valid_domains = set()
        for variant in variants:
            variant = variant.replace('(', '').replace(')', '').replace('|', '')
            if '.' in variant and not re.search(r'[^a-z0-9.-]', variant):
                valid_domains.add(variant)
        return list(valid_domains)
    except Exception:
        return []

def clean_domain_line(line):
    line = line.split('#')[0].strip()
    if not line:
        return None
    if line.startswith('regexp:'):
        regex = line[7:].strip()
        domains = generate_from_regex(regex)
        return domains if domains else None
    line = re.sub(r'^\s*-\s*', '', line)
    line = re.sub(r'^\s*(#|;|//|--).*', '', line)
    line = re.sub(r'^(full:|domain:|keyword:)', '', line)
    line = line.split('@')[0]
    line = re.sub(r'^https?://', '', line)
    line = re.sub(r'^//', '', line)
    line = re.sub(r'^www\d*\.', '', line, flags=re.IGNORECASE)
    line = line.strip()
    if not line:
        return None
    line = re.sub(r'[/:].*$', '', line)
    if re.search(r"[\\^$*+?()\[\]{}|]", line):
        return None
    try:
        parsed = urlparse('http://' + line)
        netloc = parsed.netloc.split(':')[0]
        if not netloc or '.' not in netloc:
            return None
        return netloc.lower()
    except Exception:
        return None

def filter_subdomains():
    """Удаляет поддомены из основного файла доменов"""
    if not os.path.exists(DOMAINS_FILE):
        return
        
    with open(DOMAINS_FILE, "r") as f:
        domains = [line.strip() for line in f if line.strip()]
    
    filtered_domains = filter_domains_list(domains)
    
    # Записываем отфильтрованные домены обратно в файл
    with open(DOMAINS_FILE, "w") as f:
        f.write("\n".join(filtered_domains) + "\n")

def download_content(url):
    if requests is None:
        return None
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception:
        return None

def process_domain_source(source):
    domains = set()
    if source.startswith(('http://', 'https://')):
        content = download_content(source)
        if content:
            for line in content.splitlines():
                result = clean_domain_line(line)
                if isinstance(result, list):
                    domains.update(result)
                elif result:
                    domains.add(result)
    else:
        result = clean_domain_line(source)
        if isinstance(result, list):
            domains.update(result)
        elif result:
            domains.add(result)
    return domains

def parse_v2fly_file(filename, category_domains, visited):
    if filename in visited:
        return
    visited.add(filename)
    path = os.path.join(V2FLY_DATA_DIR, filename)
    if not os.path.isfile(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("include:"):
                included_file = line.split("include:")[1].strip()
                parse_v2fly_file(included_file, category_domains, visited)
                continue
            cleaned = clean_domain_line(line)
            if isinstance(cleaned, list):
                category_domains.update(cleaned)
            elif cleaned:
                category_domains.add(cleaned)

def process_v2fly_categories(categories):
    if not categories:
        return {}
    if os.path.exists(V2FLY_CLONE_DIR):
        shutil.rmtree(V2FLY_CLONE_DIR)
    os.makedirs(os.path.dirname(V2FLY_CLONE_DIR), exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", V2FLY_REPO_URL, V2FLY_CLONE_DIR],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return {}
    category_data = {}
    for category in categories:
        visited = set()
        domains = set()
        parse_v2fly_file(category, domains, visited)
        if domains:
            category_data[category] = domains
    return category_data

def filter_domains_list(domains):
    """Фильтрует список доменов, удаляя поддомены"""
    if not domains:
        return []
    
    # Сортируем домены по количеству точек (от меньшего к большему)
    sorted_domains = sorted(set(domains), key=lambda x: x.count('.'))
    
    filtered_domains = []
    
    for domain in sorted_domains:
        # Проверяем, не является ли текущий домен поддоменом уже добавленного
        is_subdomain = False
        
        for existing_domain in filtered_domains:
            # Если домен заканчивается на "." + существующий_домен, то это поддомен
            if domain.endswith('.' + existing_domain):
                is_subdomain = True
                break
        
        # Если это не поддомен, добавляем в результат
        if not is_subdomain:
            filtered_domains.append(domain)
    
    return sorted(filtered_domains)

def save_service_domains(service_name, domains):
    service_dir = os.path.join(CATEGORIES_DIR, service_name)
    service_file = os.path.join(service_dir, f"{service_name}.lst")
    os.makedirs(service_dir, exist_ok=True)
    existing_domains = set()
    if os.path.exists(service_file):
        with open(service_file, 'r') as f:
            existing_domains = set(line.strip() for line in f if line.strip())
    all_domains = existing_domains | domains
    
    # Фильтруем поддомены для сервисного файла
    filtered_domains = filter_domains_list(list(all_domains))
    
    with open(service_file, 'w') as f:
        f.write("\n".join(filtered_domains) + "\n")
    return set(filtered_domains)

def main():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, 'rb') as f:
        config = tomllib.load(f)
    v2fly_categories = set()
    services = config.get('services', {})
    for service_name, service_config in services.items():
        if 'v2fly' in service_config:
            categories = service_config['v2fly']
            if isinstance(categories, str):
                v2fly_categories.add(categories)
            elif isinstance(categories, list):
                v2fly_categories.update(categories)
    v2fly_data = process_v2fly_categories(v2fly_categories) if v2fly_categories else {}
    all_domains = set()
    domains_to_exclude = set()
    
    for service_name, service_config in services.items():
        service_domains = set()
        urls = service_config.get('url', [])
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            domains = process_domain_source(url)
            service_domains |= domains
        domains_list = service_config.get('domains', [])
        if isinstance(domains_list, str):
            domains_list = [domains_list]
        for domain in domains_list:
            result = clean_domain_line(domain)
            if isinstance(result, list):
                service_domains.update(result)
            elif result:
                service_domains.add(result)
        if 'v2fly' in service_config:
            categories = service_config['v2fly']
            if isinstance(categories, str):
                categories = [categories]
            for category in categories:
                if category in v2fly_data:
                    service_domains |= v2fly_data[category]
        
        if service_domains:
            filtered_service_domains = save_service_domains(service_name, service_domains)
            
            # Проверяем настройку general (по умолчанию true)
            add_to_general = service_config.get('general', True)
            if isinstance(add_to_general, str):
                add_to_general = add_to_general.lower() != 'false'
            
            if add_to_general:
                all_domains |= filtered_service_domains
                with open(DOMAINS_FILE, 'a') as f:
                    f.write("\n".join(sorted(filtered_service_domains)) + "\n")
            else:
                # Если general = false, собираем домены для исключения
                domains_to_exclude |= filtered_service_domains
    
    if all_domains:
        filter_subdomains()
    
    # Удаляем домены с general = false из domains.lst
    if domains_to_exclude and os.path.exists(DOMAINS_FILE):
        with open(DOMAINS_FILE, 'r') as f:
            existing_domains = [line.strip() for line in f if line.strip()]
        
        # Фильтруем существующие домены, удаляя те, что в списке исключений
        filtered_existing = []
        for domain in existing_domains:
            should_exclude = False
            # Проверяем точное совпадение или является ли поддоменом исключаемого домена
            for exclude_domain in domains_to_exclude:
                if domain == exclude_domain or domain.endswith('.' + exclude_domain):
                    should_exclude = True
                    break
            if not should_exclude:
                filtered_existing.append(domain)
        
        # Перезаписываем файл без исключенных доменов
        with open(DOMAINS_FILE, 'w') as f:
            f.write("\n".join(sorted(set(filtered_existing))) + "\n")
    
    if os.path.exists(V2FLY_CLONE_DIR):
        shutil.rmtree(V2FLY_CLONE_DIR)

if __name__ == "__main__":
    main()
