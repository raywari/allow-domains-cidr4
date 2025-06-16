import json
import os

DOMAINS_FILE = 'domains.lst'
CIDR4_FILE = 'categories/CIDRs/CIDR4/summary-cidr4.lst'
BLOCK_DOMAINS_FILE = 'categories/Block/block-domains.lst'
BLOCK_IPS_FILE = 'categories/Block/block-ips.lst'
DOMAINS_WITHOUT_YT_FILE = 'domains-without-yt.lst'

OUTPUT_MAIN = 'categories/Rulesets/sing-box-rules/domains-cidr4.json'
OUTPUT_BLOCK = 'categories/Rulesets/sing-box-rules/block.json'
OUTPUT_WITHOUT_YT = 'categories/Rulesets/sing-box-rules/domains-cidr4-without-yt.json'

def read_lines(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def create_rules(domains, cidrs):
    return {
        "version": 3,
        "rules": [
            {
                "domain_suffix": domains,
                "ip_cidr": cidrs
            }
        ]
    }

def save_json(data, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    # Основной ruleset
    domains = read_lines(DOMAINS_FILE)
    cidrs = read_lines(CIDR4_FILE)
    main_data = create_rules(domains, cidrs)
    save_json(main_data, OUTPUT_MAIN)

    # Блокирующий ruleset
    block_domains = read_lines(BLOCK_DOMAINS_FILE)
    block_ips = read_lines(BLOCK_IPS_FILE)
    block_data = create_rules(block_domains, block_ips)
    save_json(block_data, OUTPUT_BLOCK)

    # Ruleset без YouTube
    domains_without_yt = read_lines(DOMAINS_WITHOUT_YT_FILE)
    without_yt_data = create_rules(domains_without_yt, cidrs)
    save_json(without_yt_data, OUTPUT_WITHOUT_YT)

if __name__ == "__main__":
    main()
