import os
import re
import subprocess
import shutil
from urllib.parse import urlparse
import itertools

TMP_DIR = "tmp"
REPO_URL = "https://github.com/v2fly/domain-list-community.git"
CLONED_REPO_DIR = os.path.join(TMP_DIR, "domain-list-community")
DATA_DIR = os.path.join(CLONED_REPO_DIR, "data")
SOURCES_FILE = "sources/sources-v2fly.txt"
OUTPUT_FILE = "domains.lst"

visited_files = set()

def generate_from_regex(regex):
    """Полная расшифровка регулярных выражений в возможные домены"""
    try:
        regex = regex.replace('^', '').replace('$', '')
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
    
    except:
        return None

def clean_domain_line(line):
    line = line.split('#')[0].strip()
    if not line:
        return None
    
    if line.startswith('regexp:'):
        regex = line[7:].strip()
        domains = generate_from_regex(regex)
        return domains if domains else None
    
    line = re.sub(r'^(full:|domain:|keyword:)', '', line)
    line = line.split('@')[0]
    line = re.sub(r'^https?://', '', line)
    line = re.sub(r'^//', '', line)
    line = line.strip()
    
    if not line:
        return None

    if re.search(r"[\\^$*+?()\[\]{}|]", line):
        return None
    
    try:
        parsed = urlparse('http://' + line)
        if not parsed.netloc or '.' not in parsed.netloc:
            return None
        return parsed.netloc.lower()
    except:
        return None

def parse_file(filename, domains):
    if filename in visited_files:
        return
    visited_files.add(filename)

    path = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(path):
        print(f"⚠️  Файл {path} не найден.")
        return

    with open(path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
                
            if line.startswith("include:"):
                included_file = line.split("include:")[1].strip()
                parse_file(included_file, domains)
                continue
                
            cleaned = clean_domain_line(line)
            if isinstance(cleaned, list):
                domains.update(cleaned)
            elif cleaned:
                domains.add(cleaned)

def main():
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    
    try:
        os.makedirs(TMP_DIR, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, CLONED_REPO_DIR],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        domains = set()

        if not os.path.isfile(SOURCES_FILE):
            print(f"❌ Файл {SOURCES_FILE} не найден.")
            return

        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                filename = line.strip()
                if filename:
                    parse_file(filename, domains)

        existing = set()
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing = set(line.strip() for line in f if line.strip())

        combined = sorted(existing.union(domains))
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for domain in combined:
                f.write(f"{domain}\n")

        print(f"✅ Готово. Добавлено {len(domains - existing)} новых доменов. Всего: {len(combined)}")

    except subprocess.CalledProcessError:
        print("❌ Ошибка при клонировании репозитория")
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
    finally:
        if os.path.exists(TMP_DIR):
            shutil.rmtree(TMP_DIR)
            print("🧹 Временные файлы удалены")

if __name__ == "__main__":
    main()
