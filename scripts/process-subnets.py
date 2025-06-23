#!/usr/bin/env python3
import os
import toml
import aiohttp
import asyncio
import ipaddress
from pathlib import Path

# ===== LOAD CONFIG =====
CONFIG_FILE = "scripts/config/process-subnets.toml"
with open(CONFIG_FILE) as f:
    config = toml.load(f)

SERVICES = config["services"]
SUMMARY = config["settings"]["summary"]
USER_AGENT = config["settings"]["user_agent"]
BGP_URL = config["settings"]["bgp_url"]
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

async def process_service(session, name, service_config):
    service_type = service_config["type"]

    if service_type == 'url':
        v4_url = service_config["v4_url"]
        v6_url = service_config["v6_url"]
        
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
            
    elif service_type == 'single_url':
        url = service_config["url"]
        if data := await download(session, url):
            merged_v4, merged_v6 = merge_networks(data.splitlines())
            Path(f'categories/CIDRs/CIDR4/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v4))
            Path(f'categories/CIDRs/CIDR6/services/{name}/{name.lower()}.lst').write_text('\n'.join(merged_v6))

async def process_asns(session):
    asn_services = {}
    for name, service_config in SERVICES.items():
        if service_config["type"] == "asn" and "asn" in service_config:
            asn_list = service_config["asn"]
            if isinstance(asn_list, int):
                asn_services[name] = [asn_list]
            else:
                asn_services[name] = asn_list
    
    if not asn_services:
        return

    if bgp_data := await download(session, BGP_URL):
        cidrs = {}
        for line in bgp_data.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
                
            cidr = parts[0]
            asn = parts[-1]
            
            try:
                asn_value = int(asn)
            except ValueError:
                continue
                
            for service, service_asns in asn_services.items():
                if asn_value in service_asns:
                    cidrs.setdefault(service, {'v4': set(), 'v6': set()})
                    target = 'v4' if '.' in cidr else 'v6'
                    cidrs[service][target].add(cidr)

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
        for name, service_config in SERVICES.items():
            if service_config["type"] != 'asn':
                tasks.append(process_service(session, name, service_config))
                
        await asyncio.gather(*tasks)
        await process_asns(session)
        
    make_summary()

if __name__ == '__main__':
    asyncio.run(main())
