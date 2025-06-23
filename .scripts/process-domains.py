import os
import re
import shutil
import locale
from urllib.parse import urlparse
import requests

class DomainProcessor:
    def __init__(self):
        self.set_collation()
    
    def set_collation(self):
        try:
            locale.setlocale(locale.LC_ALL, 'C')
        except locale.Error:
            os.environ['LC_ALL'] = 'C'

    def clean_line(self, line):
        line = re.sub(r'^\s*-\s*', '', line)
        line = re.sub(r'^\s*(#|;|//|--).*', '', line)
        line = re.sub(r'^full:', '', line)
        line = re.sub(r'^(https?://|//)', '', line)
        line = re.sub(r'[/:].*$', '', line)
        line = re.sub(r'^www[2-9]?\.', '', line)
        return line.strip()

    def read_lines(self, file_path):
        with open(file_path, 'r') as f:
            return [self.clean_line(line) for line in f if self.clean_line(line)]

    def write_lines(self, file_path, lines):
        with open(file_path, 'w') as f:
            f.write('\n'.join(sorted(set(lines), key=locale.strxfrm)) + '\n')

    def sort_domains(self, domains):
        return sorted(set(domains), key=lambda x: (locale.strxfrm(x), x))

    def filter_subdomains(self, domains):
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
        
        return self.sort_domains(filtered)

    def compare_files(self, list1, list2):
        i = j = 0
        unique1 = []
        unique2 = []
        common = []
        
        while i < len(list1) and j < len(list2):
            a, b = list1[i], list2[j]
            cmp = locale.strcoll(a, b)
            
            if cmp < 0:
                unique1.append(a)
                i += 1
            elif cmp > 0:
                unique2.append(b)
                j += 1
            else:
                common.append(a)
                i += 1
                j += 1
        
        unique1.extend(list1[i:])
        unique2.extend(list2[j:])
        return unique1, unique2, common

class DomainComparator(DomainProcessor):
    def __init__(self, sources_path, output_dir):
        super().__init__()
        self.sources_path = sources_path
        self.output_dir = output_dir
        self.base_tmp = './tmp'
        self.primary_domains = set()

    def process_external_source(self, url):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            
            content = re.sub(r'(?m)^\s*#.*$|^\s*$|^[0-9.]+\s+', '', resp.text)
            domains = [
                self.clean_line(line)
                for line in re.sub(r'\s+', '\n', content).split('\n')
                if re.match(r'^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', line)
            ]
            
            filtered = []
            for domain in domains:
                d = domain
                is_sub = False
                while '.' in d:
                    d = d.split('.', 1)[1]
                    if d in self.primary_domains:
                        is_sub = True
                        break
                if not is_sub:
                    filtered.append(domain)
            
            return self.sort_domains(filtered)
            
        except Exception as e:
            print(f'Error processing {url}: {e}')
            return []

    def generate_reports(self, source_url, key, external_domains, primary_sorted):
        external_sorted = self.sort_domains(external_domains)
        missing, presence, _ = self.compare_files(external_sorted, primary_sorted)
        
        reports = {
            'missing': missing,
            'presence': presence
        }
        
        for report_type, data in reports.items():
            if data:
                report_file = os.path.join(
                    self.output_dir, 
                    f'{report_type}-domains.txt'
                )
                with open(report_file, 'a') as f:
                    f.write(f"# {report_type.capitalize()} domains\n")
                    f.write(f"# Source: {source_url}\n\n")
                    f.write('\n'.join([f'- {d}' for d in data]) + '\n\n')

    def process_sources(self, primary_domains):
        self.primary_domains = set(primary_domains)
        primary_sorted = self.sort_domains(primary_domains)
        
        missing_report = os.path.join(self.output_dir, 'missing-domains.txt')
        presence_report = os.path.join(self.output_dir, 'presence-domains.txt')
        for report_file in [missing_report, presence_report]:
            if os.path.exists(report_file):
                os.remove(report_file)
        
        with open(self.sources_path, 'r') as f:
            source_urls = [
                line.split('#')[0].strip()
                for line in f if line.strip() and not line.startswith('#')
            ]
        
        for url in source_urls:
            external_domains = self.process_external_source(url)
            if external_domains:
                self.generate_reports(
                    url, 
                    self.get_source_key(url), 
                    external_domains, 
                    primary_sorted
                )

    def get_source_key(self, url):
        return re.sub(
            r'https?://|[/?.&]', '_',
            url.split('#')[0].strip()
        ).strip('_').replace('.', '_')

def main():
    processor = DomainProcessor()
    
    domains = processor.read_lines('domains.lst')
    filtered_domains = processor.filter_subdomains(domains)
    processor.write_lines('domains.lst', filtered_domains)
    
    comparator = DomainComparator(
        '.scripts/sources/sources-domains.txt',
        'categories/Compared-Domains'
    )
    comparator.process_sources(filtered_domains)
    
    yt_domains = processor.read_lines('categories/Services/youtube/youtube-domains.lst')
    non_yt = [d for d in filtered_domains if d not in yt_domains]
    processor.write_lines('domains-without-yt.lst', non_yt)

if __name__ == '__main__':
    main()
