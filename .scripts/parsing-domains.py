#!/usr/bin/env python3
import os
import re
import shutil
import asyncio
import aiohttp
import aiofiles
from urllib.parse import urlparse
try:
    import tomllib
except ImportError:
    import toml as tomllib

V2FLY_REPO_URL = "https://github.com/v2fly/domain-list-community.git"
V2FLY_CLONE_DIR = "tmp/domain-list-community"
V2FLY_DATA_DIR = os.path.join(V2FLY_CLONE_DIR, "data")
CONFIG_PATH = ".scripts/config/parsing-domains.toml"
DOMAINS_FILE = "domains.lst"
CATEGORIES_DIR = "categories/Services"
GROUPS_DIR = "categories/Groups"

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
        variants = [''] if not regex.startswith('|') else []
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

def filter_domains_list(domains):
    if not domains:
        return []

    sorted_domains = sorted(set(domains), key=lambda x: x.count('.'))
    filtered_domains = []

    for domain in sorted_domains:
        is_subdomain = False
        for existing_domain in filtered_domains:
            if domain.endswith('.' + existing_domain):
                is_subdomain = True
                break
        if not is_subdomain:
            filtered_domains.append(domain)

    return sorted(filtered_domains)

async def download_content(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.text()
    except Exception:
        return None

async def process_domain_source(source):
    domains = set()
    if source.startswith(('http://', 'https://')):
        content = await download_content(source)
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

async def parse_v2fly_file(filename, visited=None):
    if visited is None:
        visited = set()
    if filename in visited:
        return set()
    visited.add(filename)
    path = os.path.join(V2FLY_DATA_DIR, filename)
    if not os.path.isfile(path):
        return set()

    domains = set()
    async with aiofiles.open(path, 'r', encoding='utf-8') as f:
        for raw_line in await f.readlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("include:"):
                included_file = line.split("include:")[1].strip()
                included_domains = await parse_v2fly_file(included_file, visited)
                domains |= included_domains
            else:
                cleaned = clean_domain_line(line)
                if isinstance(cleaned, list):
                    domains |= set(cleaned)
                elif cleaned:
                    domains.add(cleaned)
    return domains

async def process_v2fly_categories(categories):
    if not categories:
        return {}
    if os.path.exists(V2FLY_CLONE_DIR):
        shutil.rmtree(V2FLY_CLONE_DIR, ignore_errors=True)
    os.makedirs(os.path.dirname(V2FLY_CLONE_DIR), exist_ok=True)

    try:
        process = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", V2FLY_REPO_URL, V2FLY_CLONE_DIR,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await process.wait()
        if process.returncode != 0:
            return {}
    except Exception:
        return {}

    tasks = [parse_v2fly_file(category) for category in categories]
    results = await asyncio.gather(*tasks)

    category_data = {}
    for i, category in enumerate(categories):
        if results[i]:
            category_data[category] = results[i]
    return category_data

async def save_service_domains(service_name, domains):
    service_dir = os.path.join(CATEGORIES_DIR, service_name)
    service_file = os.path.join(service_dir, f"{service_name}.lst")
    os.makedirs(service_dir, exist_ok=True)

    existing_domains = set()
    if os.path.exists(service_file):
        async with aiofiles.open(service_file, 'r') as f:
            content = await f.read()
            existing_domains = set(line.strip() for line in content.splitlines() if line.strip())

    all_domains = existing_domains | domains
    filtered_domains = filter_domains_list(list(all_domains))

    async with aiofiles.open(service_file, 'w') as f:
        await f.write("\n".join(filtered_domains) + "\n")

    return set(filtered_domains)

async def save_group_domains(group_name, domains):
    group_dir = os.path.join(GROUPS_DIR, group_name)
    group_file = os.path.join(group_dir, f"{group_name}.lst")
    os.makedirs(group_dir, exist_ok=True)

    existing_domains = set()
    if os.path.exists(group_file):
        async with aiofiles.open(group_file, 'r') as f:
            content = await f.read()
            existing_domains = set(line.strip() for line in content.splitlines() if line.strip())

    all_domains = existing_domains | set(domains)
    filtered_domains = filter_domains_list(list(all_domains))

    async with aiofiles.open(group_file, 'w') as f:
        await f.write("\n".join(filtered_domains) + "\n")

    return set(filtered_domains)

async def process_excluded_service(service_name, service_config):
    service_excluded_domains = set()

    urls = service_config.get('url', [])
    if isinstance(urls, str):
        urls = [urls]

    url_tasks = [process_domain_source(url) for url in urls]
    url_results = await asyncio.gather(*url_tasks)
    for domains in url_results:
        service_excluded_domains |= domains

    domains_list = service_config.get('domains', [])
    if isinstance(domains_list, str):
        domains_list = [domains_list]
    for domain in domains_list:
        result = clean_domain_line(domain)
        if isinstance(result, list):
            service_excluded_domains.update(result)
        elif result:
            service_excluded_domains.add(result)

    if 'v2fly' in service_config:
        categories = service_config['v2fly']
        if isinstance(categories, str):
            categories = [categories]

        excluded_v2fly_data = await process_v2fly_categories(categories)
        for category in categories:
            if category in excluded_v2fly_data:
                service_excluded_domains |= excluded_v2fly_data[category]

    if service_excluded_domains:
        await save_service_domains(service_name, service_excluded_domains)

    return service_excluded_domains

async def process_non_excluded_service(service_name, service_config, v2fly_data, all_excluded_domains):
    service_domains = set()

    urls = service_config.get('url', [])
    if isinstance(urls, str):
        urls = [urls]

    url_tasks = [process_domain_source(url) for url in urls]
    url_results = await asyncio.gather(*url_tasks)
    for domains in url_results:
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
                category_domains = v2fly_data[category] - all_excluded_domains
                service_domains |= category_domains

    service_domains = service_domains - all_excluded_domains

    if service_domains:
        filtered_service_domains = await save_service_domains(service_name, service_domains)
        return filtered_service_domains
    return set()

def should_include_service(service_general, group_general):
    if service_general is False:
        return False
    if service_general is True:
        return True
    if service_general is None:
        service_general = True

    if group_general is None:
        group_general = True

    return service_general and group_general

async def process_group(group_name, group_config, v2fly_data, service_domains_dict, service_general_dict):
    group_domains = set()

    # Direct domains
    domains_list = group_config.get('domains', [])
    if isinstance(domains_list, str):
        domains_list = [domains_list]
    for domain in domains_list:
        result = clean_domain_line(domain)
        if isinstance(result, list):
            group_domains.update(result)
        elif result:
            group_domains.add(result)

    # URLs
    urls = group_config.get('url', [])
    if isinstance(urls, str):
        urls = [urls]
    url_tasks = [process_domain_source(url) for url in urls]
    url_results = await asyncio.gather(*url_tasks)
    for domains in url_results:
        group_domains |= domains

    # v2fly
    if 'v2fly' in group_config:
        categories = group_config['v2fly']
        if isinstance(categories, str):
            categories = [categories]
        for category in categories:
            if category in v2fly_data:
                group_domains |= v2fly_data[category]

    # include сервисы
    include_list = group_config.get('include', [])
    if isinstance(include_list, str):
        include_list = [include_list]

    group_general = group_config.get('general')
    if group_general is None:
        group_general = True
    elif isinstance(group_general, str):
        group_general = group_general.lower() == 'true'

    # Создаем нормализованный словарь для сервисов
    normalized_service_general_dict = {k.lower(): v for k, v in service_general_dict.items()}
    normalized_service_domains_dict = {k.lower(): v for k, v in service_domains_dict.items()}

    for service_name in include_list:
        key = service_name.strip().lower()
        if key in normalized_service_general_dict:
            service_domains = normalized_service_domains_dict.get(key, set())
            service_general = normalized_service_general_dict[key]

            if should_include_service(service_general, group_general):
                group_domains |= service_domains
        else:
            print(f"Warning: Service '{service_name}' not found in configuration")

    filtered_domains = filter_domains_list(list(group_domains))

    if group_general:
        await save_group_domains(group_name, filtered_domains)

    return set(filtered_domains), group_general

async def async_main():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    async with aiofiles.open(CONFIG_PATH, 'rb') as f:
        content = await f.read()
        config = tomllib.loads(content.decode('utf-8'))

    services = config.get('services', {})
    groups = config.get('groups', {})

    # Словари для хранения данных сервисов
    service_domains_dict = {}
    service_general_dict = {}
    all_excluded_domains = set()

    # Собираем все v2fly категории
    v2fly_categories = set()
    for service_config in services.values():
        if 'v2fly' in service_config:
            categories = service_config['v2fly']
            if isinstance(categories, str):
                v2fly_categories.add(categories)
            elif isinstance(categories, list):
                v2fly_categories.update(categories)
    for group_config in groups.values():
        if 'v2fly' in group_config:
            categories = group_config['v2fly']
            if isinstance(categories, str):
                v2fly_categories.add(categories)
            elif isinstance(categories, list):
                v2fly_categories.update(categories)

    # Обрабатываем v2fly категории
    v2fly_data = {}
    if v2fly_categories:
        v2fly_data = await process_v2fly_categories(list(v2fly_categories))

    # Определяем флаги general для сервисов (регистронезависимо)
    for service_name, service_config in services.items():
        flag = service_config.get('general', True)
        if isinstance(flag, str):
            flag = flag.strip().lower() != 'false'
        service_general_dict[service_name.lower()] = flag

    # Собираем домены всех исключенных сервисов
    for service_name, service_config in services.items():
        service_name_lower = service_name.lower()
        if not service_general_dict.get(service_name_lower, True):
            # Обрабатываем URL
            urls = service_config.get('url', [])
            if isinstance(urls, str):
                urls = [urls]
            url_tasks = [process_domain_source(url) for url in urls]
            url_results = await asyncio.gather(*url_tasks)
            for domains in url_results:
                all_excluded_domains |= domains

            # Обрабатываем явные домены
            domains_list = service_config.get('domains', [])
            if isinstance(domains_list, str):
                domains_list = [domains_list]
            for domain in domains_list:
                result = clean_domain_line(domain)
                if isinstance(result, list):
                    all_excluded_domains.update(result)
                elif result:
                    all_excluded_domains.add(result)

            # Обрабатываем v2fly категории
            if 'v2fly' in service_config:
                categories = service_config['v2fly']
                if isinstance(categories, str):
                    categories = [categories]
                for category in categories:
                    if category in v2fly_data:
                        all_excluded_domains |= v2fly_data[category]

    # Обрабатываем обычные сервисы (non-excluded)
    for service_name, service_config in services.items():
        service_name_lower = service_name.lower()
        if service_general_dict.get(service_name_lower, True):
            service_domains = set()

            # Обрабатываем URL
            urls = service_config.get('url', [])
            if isinstance(urls, str):
                urls = [urls]
            url_tasks = [process_domain_source(url) for url in urls]
            url_results = await asyncio.gather(*url_tasks)
            for domains in url_results:
                service_domains |= domains

            # Обрабатываем явные домены
            domains_list = service_config.get('domains', [])
            if isinstance(domains_list, str):
                domains_list = [domains_list]
            for domain in domains_list:
                result = clean_domain_line(domain)
                if isinstance(result, list):
                    service_domains.update(result)
                elif result:
                    service_domains.add(result)

            # Обрабатываем v2fly категории
            if 'v2fly' in service_config:
                categories = service_config['v2fly']
                if isinstance(categories, str):
                    categories = [categories]
                for category in categories:
                    if category in v2fly_data:
                        service_domains |= v2fly_data[category]

            # Исключаем домены из excluded сервисов
            service_domains -= all_excluded_domains

            if service_domains:
                filtered_domains = await save_service_domains(service_name, service_domains)
                service_domains_dict[service_name_lower] = filtered_domains

    # Обрабатываем существующие домены
    existing_domains = set()
    if os.path.exists(DOMAINS_FILE):
        async with aiofiles.open(DOMAINS_FILE, 'r') as f:
            content = await f.read()
            existing_domains = set(line.strip() for line in content.splitlines() if line.strip())

    # Фильтруем существующие домены
    filtered_personal_domains = existing_domains - all_excluded_domains

    # Собираем все разрешенные домены
    all_allowed_domains = set()
    for domains in service_domains_dict.values():
        all_allowed_domains |= domains
    all_allowed_domains |= filtered_personal_domains

    # Обрабатываем группы
    if groups:
        group_tasks = []
        for group_name, group_config in groups.items():
            group_tasks.append(process_group(
                group_name, 
                group_config, 
                v2fly_data,
                service_domains_dict,
                service_general_dict
            ))

        group_results = await asyncio.gather(*group_tasks)

        for domains, group_general in group_results:
            if group_general:
                all_allowed_domains |= domains

    # ЖЕСТКАЯ ФИЛЬТРАЦИЯ В КОНЦЕ
    final_domains = set()
    for domain in all_allowed_domains:
        # Проверяем, не является ли домен поддоменом исключенного
        is_excluded = False
        for excluded_domain in all_excluded_domains:
            if (domain == excluded_domain or 
                domain.endswith('.' + excluded_domain) or 
                excluded_domain.endswith('.' + domain)):
                is_excluded = True
                break
        if not is_excluded:
            final_domains.add(domain)

    # Сохраняем финальные домены
    if final_domains:
        filtered_final_domains = filter_domains_list(list(final_domains))
        async with aiofiles.open(DOMAINS_FILE, 'w') as f:
            await f.write("\n".join(sorted(filtered_final_domains)) + "\n")

async def main_async():
    await async_main()
    if os.path.exists(V2FLY_CLONE_DIR):
        shutil.rmtree(V2FLY_CLONE_DIR, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(main_async())