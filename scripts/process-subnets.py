#!/usr/bin/env python3
import os
import json
import aiohttp
import asyncio
import ipaddress
from pathlib import Path

# ===== LOAD CONFIG =====
CONFIG_FILE = "scripts/config/process-subnets.json"
with open(CONFIG_FILE) as f:
    config = json.load(f)

SERVICES = config["SERVICES"]
SUMMARY = config["SUMMARY"]
USER_AGENT = config["USER_AGENT"]
BGP_URL = config["BGP_URL"]
# ===== END SETTINGS =====

def merge_networks(network_list):
    if not network_list:
        return [], []
    
    v4_nets = []
    v6_nets = []
    
    for net_str in network_list:
        net_str = net_str.strip()
        if not net_str:
            continue
            
        try:
            if '.' in net_str:
                v4_nets.append(ipaddress.IPv4Network(net_str))
            elif ':' in net_str:
                v6_nets.append(ipaddress.IPv6Network(net_str))
        except Exception as e:
            print(f"Invalid network skipped: {net_str} - {e}")
    
    merged_v4 = [str(net) for net in ipaddress.collapse_addresses(v4_nets)] if v4_nets else []
    merged_v6 = [str(net) for net in ipaddress.collapse_addresses(v6_nets)] if v6_nets else []
    
    return merged_v4, merged_v6

def setup_dirs():
    for name in SERVICES:
        Path(f'categories/CIDRs/CIDR4/services/{name}').mkdir(parents=True, exist_ok=True)
        Path(f'categories/CIDRs/CIDR6/services/{name}').mkdir(parents=True, exist_ok=True)

async def download(session, url, params=None):
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
            r.raise_for_status()
            return await r.text()
    except Exception as e:
        print(f"Download error: {url} - {e}")
        return None

async def process_service(session, name, config):
    service_type, *args = config

    if service_type == 'url':
        v4_url, v6_url = args
        tasks = [
            download(session, v4_url),
            download(session, v6_url)
        ]
        results = await asyncio.gather(*tasks)
        
        if results[0]:
            merged_v4, _ = merge_networks(results[0].splitlines())
            Path(f'categories/CIDRs/CIDR4/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v4))
        if results[1]:
            _, merged_v6 = merge_networks(results[1].splitlines())
            Path(f'categories/CIDRs/CIDR6/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v6))
            
    elif service_type == 'url_params':
        base_url = args[0]
        tasks = [
            download(session, base_url.format(cidr='cidr4')),
            download(session, base_url.format(cidr='cidr6'))
        ]
        results = await asyncio.gather(*tasks)
        
        if results[0]:
            merged_v4, _ = merge_networks(results[0].splitlines())
            Path(f'categories/CIDRs/CIDR4/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v4))
        if results[1]:
            _, merged_v6 = merge_networks(results[1].splitlines())
            Path(f'categories/CIDRs/CIDR6/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v6))
            
    elif service_type == 'single_url':
        if data := await download(session, args[0]):
            merged_v4, merged_v6 = merge_networks(data.splitlines())
            Path(f'categories/CIDRs/CIDR4/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v4))
            Path(f'categories/CIDRs/CIDR6/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v6))

async def process_asns(session):
    asn_map = {name: config[1] for name, config in SERVICES.items() if config[0] == 'asn'}
    if not asn_map:
        return

    if bgp_data := await download(session, BGP_URL):
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
                merged_v4, _ = merge_networks(sorted(ips['v4']))
                Path(f'categories/CIDRs/CIDR4/services/{service}/{service.lower()}.lst').write_text('\n'.join(merged_v4))
            if ips['v6']:
                _, merged_v6 = merge_networks(sorted(ips['v6']))
                Path(f'categories/CIDRs/CIDR6/services/{service}/{service.lower()}.lst').write_text('\n'.join(merged_v6))

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

    merged_v4, _ = merge_networks(sorted(all_ips_v4))
    _, merged_v6 = merge_networks(sorted(all_ips_v6))

    Path(f'categories/CIDRs/CIDR4/summary-cidr4.lst').write_text('\n'.join(merged_v4))
    Path(f'categories/CIDRs/CIDR6/summary-cidr6.lst').write_text('\n'.join(merged_v6))

    combined_ips = sorted(merged_v4 + merged_v6)
    Path(f'categories/CIDRs/summary-cidrs.lst').write_text('\n'.join(combined_ips))

async def main():
    setup_dirs()
    
    async with aiohttp.ClientSession(headers={'User-Agent': USER_AGENT}) as session:
        tasks = []
        for name, config in SERVICES.items():
            if config[0] != 'asn':
                tasks.append(process_service(session, name, config))
                
        await asyncio.gather(*tasks)
        await process_asns(session)
        
    make_summary()

if __name__ == '__main__':
    asyncio.run(main())
