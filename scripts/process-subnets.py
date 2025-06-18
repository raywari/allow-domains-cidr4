#!/usr/bin/env python3 
import os 
import requests 
import ipaddress
from pathlib import Path 
 
# ===== SETTINGS =====
SERVICES = {
    'Cloudflare-ECH': ('url', 'https://www.cloudflare.com/ips-v4', 'https://www.cloudflare.com/ips-v6'),
    'Discord': ('url_params', 'https://iplist.opencck.org/?format=text&data={cidr}&site=discord.gg&site=discord.media'),
    'Telegram': ('single_url', 'https://core.telegram.org/resources/cidr.txt'), 
    'Meta': ('asn', 32934),
    'X-Twitter': ('asn', 13414), 
    'Hetzner': ('asn', 24940),
    'OVH': ('asn', 16276), 
    'Amazon': ('asn', 16509),
}
SUMMARY = ['Cloudflare-ECH', 'Meta', 'X-Twitter']
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BGP_URL = "https://bgp.tools/table.txt" 
# ===== END SETTINGS =====
 
def merge_networks(network_list):
    if not network_list:
        return []
 
    try:
        if ':' in network_list[0]:
            networks = [ipaddress.IPv6Network(net) for net in network_list]
        else:
            networks = [ipaddress.IPv4Network(net) for net in network_list]
 
        return [str(net) for net in ipaddress.collapse_addresses(networks)]
    except Exception as e:
        print(f"Ошибка объединения подсетей: {e}")
        return network_list
 
def setup_dirs():
    for name in SERVICES:
        Path(f'categories/CIDRs/CIDR4/services/{name}').mkdir(parents=True, exist_ok=True)
        Path(f'categories/CIDRs/CIDR6/services/{name}').mkdir(parents=True, exist_ok=True)
 
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
            merged = merge_networks(data.splitlines())
            Path(f'categories/CIDRs/CIDR4/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged))
        if data := download(args[1]): 
            merged = merge_networks(data.splitlines())
            Path(f'categories/CIDRs/CIDR6/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged))
    elif service_type == 'url_params': 
        if data := download(args[0].format(cidr='cidr4')): 
            merged = merge_networks(data.splitlines())
            Path(f'categories/CIDRs/CIDR4/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged))
        if data := download(args[0].format(cidr='cidr6')): 
            merged = merge_networks(data.splitlines())
            Path(f'categories/CIDRs/CIDR6/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged))
    elif service_type == 'single_url': 
        if data := download(args[0]): 
            v4_lines = [line for line in data.splitlines() if '.' in line]
            v6_lines = [line for line in data.splitlines() if ':' in line]
 
            merged_v4 = merge_networks(v4_lines)
            merged_v6 = merge_networks(v6_lines)
 
            Path(f'categories/CIDRs/CIDR4/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v4)) 
            Path(f'categories/CIDRs/CIDR6/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v6)) 
 
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
            merged = merge_networks(sorted(ips['v4']))
            Path(f'categories/CIDRs/CIDR4/services/{service}/{service.lower()}.lst').write_text('\n'.join(merged)) 
        if ips['v6']: 
            merged = merge_networks(sorted(ips['v6']))
            Path(f'categories/CIDRs/CIDR6/services/{service}/{service.lower()}.lst').write_text('\n'.join(merged)) 
 
def make_summary():
    all_ips_v4 = set()
    all_ips_v6 = set()
 
    for service in SUMMARY:
        file_v4 = Path(f'categories/CIDRs/CIDR4/services/{service}/{service.lower()}.lst')
        if file_v4.exists():
            all_ips_v4.update(file_v4.read_text().splitlines())
 
        file_v6 = Path(f'categories/CIDRs/CIDR6/services/{service}/{service.lower()}.lst')
        if file_v6.exists():
            all_ips_v6.update(file_v6.read_text().splitlines())
 
    merged_v4 = merge_networks(sorted(all_ips_v4))
    merged_v6 = merge_networks(sorted(all_ips_v6))
 
    Path(f'categories/CIDRs/CIDR4/summary-cidr4.lst').write_text('\n'.join(merged_v4))
    Path(f'categories/CIDRs/CIDR6/summary-cidr6.lst').write_text('\n'.join(merged_v6))
 
    combined_ips = sorted(merged_v4 + merged_v6)
    Path(f'categories/CIDRs/summary-cidrs.lst').write_text('\n'.join(combined_ips))
 
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