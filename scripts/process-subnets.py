#!/usr/bin/env python3
import os
import requests
from pathlib import Path

# ===== SETTINGS =====
SERVICES = {
    'Cloudflare-ECH': ('url', 'https://www.cloudflare.com/ips-v4', 'https://www.cloudflare.com/ips-v6'),
    'Discord': ('url_params', 'https://iplist.opencck.org/?format=text&data={cidr}&site=discord.gg&site=discord.media'),
    'Telegram': ('single_url', 'https://core.telegram.org/resources/cidr.txt'),
    'Meta': ('asn', 32934),
    'Twitter': ('asn', 13414),
    'Hetzner': ('asn', 24940),
    'OVH': ('asn', 16276),
    'Amazon': ('asn', 16509),
}

SUMMARY = ['Cloudflare-ECH', 'Meta', 'Twitter']

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BGP_URL = "https://bgp.tools/table.txt"
# ===== END SETTINGS =====

def setup_dirs():
    for name in SERVICES:
        Path(f'categories/CIDR4/services/{name}').mkdir(parents=True, exist_ok=True)
        Path(f'categories/CIDR6/services/{name}').mkdir(parents=True, exist_ok=True)

def download(url, params=None):
    try:
        r = requests.get(url, params=params, headers={'User-Agent': USER_AGENT}, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def process_service(name, config):
    service_type, *args = config
    
    if service_type == 'url':
        if data := download(args[0]):
            Path(f'categories/CIDR4/services/{name}/{name.lower()}.lst').write_text(data)
        if data := download(args[1]):
            Path(f'categories/CIDR6/services/{name}/{name.lower()}.lst').write_text(data)
    
    elif service_type == 'url_params':
        if data := download(args[0].format(cidr='cidr4')):
            Path(f'categories/CIDR4/services/{name}/{name.lower()}.lst').write_text(data)
        if data := download(args[0].format(cidr='cidr6')):
            Path(f'categories/CIDR6/services/{name}/{name.lower()}.lst').write_text(data)
    
    elif service_type == 'single_url':
        if data := download(args[0]):
            v4 = '\n'.join(sorted({line for line in data.splitlines() if '.' in line}))
            v6 = '\n'.join(sorted({line for line in data.splitlines() if ':' in line}))
            Path(f'categories/CIDR4/services/{name}/{name.lower()}.lst').write_text(v4)
            Path(f'categories/CIDR6/services/{name}/{name.lower()}.lst').write_text(v6)

def process_asns(bgp_data):
    asn_map = {name: config[1] for name, config in SERVICES.items() if config[0] == 'asn'}
    if not asn_map:
        return
    
    cidrs = {}
    for line in bgp_data.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        cidr, asn = parts[0], parts[-1]
        if asn in map(str, asn_map.values()):
            service = next(k for k, v in asn_map.items() if v == int(asn))
            cidrs.setdefault(service, {'v4': set(), 'v6': set()})
            (cidrs[service]['v4'] if '.' in cidr else cidrs[service]['v6']).add(cidr)
    
    for service, ips in cidrs.items():
        if ips['v4']:
            Path(f'categories/CIDR4/services/{service}/{service.lower()}.lst').write_text('\n'.join(sorted(ips['v4'])))
        if ips['v6']:
            Path(f'categories/CIDR6/services/{service}/{service.lower()}.lst').write_text('\n'.join(sorted(ips['v6'])))

def make_summary():
    for cidr in ['CIDR4', 'CIDR6']:
        all_ips = set()
        for service in SUMMARY:
            file = Path(f'categories/{cidr}/services/{service}/{service.lower()}.lst')
            if file.exists():
                all_ips.update(file.read_text().splitlines())
        Path(f'categories/{cidr}/summary.lst').write_text('\n'.join(sorted(all_ips)))

def main():
    setup_dirs()
    
    for name, config in SERVICES.items():
        if config[0] != 'asn':
            process_service(name, config)

    if bgp_data := download(BGP_URL):
        process_asns(bgp_data)

    make_summary()

if __name__ == '__main__':
    main()
