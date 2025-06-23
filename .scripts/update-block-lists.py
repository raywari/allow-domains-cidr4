import os
import re
import requests
from tempfile import NamedTemporaryFile

def setup_directories():
    os.makedirs("categories/Block", exist_ok=True)
    os.makedirs("sources", exist_ok=True)
    os.chdir("categories/Block")

def validate_entries():
    ip_regex = re.compile(r'^(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.'
                          r'(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.'
                          r'(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.'
                          r'(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])$')

    for list_type in ["block-ips.lst", "block-domains.lst"]:
        if not os.path.exists(list_type):
            open(list_type, "w").close()

        with open(list_type, "r+") as f:
            lines = [line.strip() for line in f if line.strip()]
            f.seek(0)
            f.truncate()

            cleaned = []
            for line in lines:
                clean_line = re.sub(r'[^\w\.-]', '', line)
                if list_type == "block-ips.lst" and ip_regex.match(clean_line):
                    cleaned.append(clean_line)
                elif list_type == "block-domains.lst":
                    cleaned.append(clean_line.lower())

            f.write("\n".join(sorted(set(cleaned))) + "\n")

def fetch_external_data():
    temp_file = NamedTemporaryFile(delete=False, mode="w+", encoding='utf-8')

    with open("../../.scripts/sources/sources-block.txt", "r", encoding='utf-8') as sources:
        for url in sources:
            url = url.strip()
            if not url or url.startswith('#'):
                continue

            try:
                response = requests.get(url, timeout=15)
                response.raise_for_status()

                for line in response.text.splitlines():
                    clean_line = re.sub(r'#.*$', '', line).strip()
                    clean_line = re.sub(r'^(0\.0\.0\.0|127\.0\.0\.1|\*\.?)\s*', '', clean_line)
                    parts = re.split(r'\s+', clean_line)

                    for part in parts:
                        part = re.sub(r'[^\w\.-]', '', part)
                        if part and not part.startswith(('http://', 'https://')):
                            temp_file.write(part + "\n")
            except Exception as e:
                print(f"Error processing {url}: {str(e)}")

    temp_file.close()
    return temp_file.name

def update_lists(temp_file):
    ip_regex = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    domain_regex = re.compile(r'^([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$')

    with open(temp_file, 'r', encoding='utf-8') as tf:
        data = tf.read().splitlines()

    ips = set()
    domains = set()

    for item in data:
        item = item.strip().lower()
        if ip_regex.match(item):
            ips.add(item)
        elif domain_regex.match(item):
            domains.add(item)

    with open("block-ips.lst", "a") as f:
        f.write("\n".join(sorted(ips)) + "\n")

    with open("block-domains.lst", "a") as f:
        f.write("\n".join(sorted(domains)) + "\n")

def filter_subdomains():
    def sort_domains(domains):
        return sorted(set(domains))

    def custom_filter(domains):
        sorted_domains = sorted(domains, key=lambda x: x.count('.'))
        keep = set()
        filtered = []

        for domain in sorted_domains:
            parents = set()
            d = domain
            while '.' in d:
                d = d.split('.', 1)[1]
                parents.add(d)

            if not parents & keep:
                filtered.append(domain)
                keep.add(domain)

        return sort_domains(filtered)

    with open("block-domains.lst", "r+") as f:
        domains = [line.strip() for line in f if line.strip()]
        filtered = custom_filter(domains)
        f.seek(0)
        f.truncate()
        f.write("\n".join(filtered) + "\n")

def final_processing():
    filter_subdomains()

    for fname in ["block-ips.lst", "block-domains.lst"]:
        with open(fname, "r+") as f:
            lines = sorted(set(line.strip() for line in f if line.strip()))
            f.seek(0)
            f.truncate()
            f.write("\n".join(lines) + "\n")

    with open("hosts", "w") as f:
        f.write("127.0.0.1 localhost\n")
        f.write("::1 localhost\n\n")

        with open("block-ips.lst") as ips:
            for line in ips:
                f.write(f"0.0.0.0 {line.strip()}\n")

        with open("block-domains.lst") as domains:
            for line in domains:
                f.write(f"0.0.0.0 {line.strip()}\n")

def main():
    original_dir = os.getcwd()
    temp_file = None
    try:
        setup_directories()
        validate_entries()
        temp_file = fetch_external_data()
        update_lists(temp_file)
        final_processing()
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        os.chdir(original_dir)
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == "__main__":
    main()