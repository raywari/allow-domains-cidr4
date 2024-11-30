import sublist3r
import threading
import time
import socket
import requests
import ipwhois

# Функция для поиска поддоменов с брутфорсом
def find_subdomains(domain):
    subdomains = []

    # Включаем брутфорс, указываем поисковые системы, отключаем цветной вывод
    def target():
        nonlocal subdomains
        subdomains = sublist3r.main(
            domain,
            threads=40,               # Количество потоков
            savefile=None,            # Не сохраняем в файл
            ports=None,               # Не указываем порты для сканирования
            silent=False,             # Выводим процесс
            verbose=True,             # Показываем результаты в реальном времени
            enable_bruteforce=True,   # Включаем брутфорс
            engines='google,bing,yahoo'  # Используем поисковые системы как строку, разделенную запятой
        )

    # Запуск потока, который будет выполнять поиск поддоменов
    thread = threading.Thread(target=target)
    thread.start()

    # Таймер на 15 минут (900 секунд)
    thread.join(timeout=900)  # Ожидаем завершения работы потока или 15 минут

    if thread.is_alive():
        print(f"Время работы поиска поддоменов для {domain} истекло (15 минут).")
        return []  # Возвращаем пустой список, если время истекло
    
    return subdomains

# Функция для получения CIDR-диапазонов для домена через IPWhois
def get_cidr_ranges(domain):
    cidr_ranges = []
    try:
        # Получаем IP-адрес для домена
        ip_address = socket.gethostbyname(domain)
        print(f"IP-адрес для {domain}: {ip_address}")
        
        # Используем ipwhois для получения информации о диапазоне CIDR
        ip = ipwhois.IPWhois(ip_address)
        result = ip.lookup_rdap()

        # Извлекаем CIDR-диапазоны из результата
        for network in result.get('network', {}).get('cidr', []):
            cidr_ranges.append(network)
        
    except Exception as e:
        print(f"Ошибка при получении CIDR для {domain}: {e}")

    return cidr_ranges

# Список доменов, связанных с Telegram
telegram_domains = [
    'telegram.org',
    't.me',
    'web.telegram.org',
    'api.telegram.org',
    'desktop.telegram.org',
    'my.telegram.org',
    'blog.telegram.org'
]

# Поиск поддоменов и CIDR для всех доменов, связанных с Telegram
all_subdomains = {}
all_cidr = {}

for domain in telegram_domains:
    print(f"\nНачинаем поиск поддоменов для {domain}...")
    subdomains = find_subdomains(domain)
    all_subdomains[domain] = subdomains
    
    print(f"Начинаем поиск CIDR для {domain}...")
    cidr_ranges = get_cidr_ranges(domain)
    all_cidr[domain] = cidr_ranges

# Вывод результатов
for domain, subdomains in all_subdomains.items():
    print(f"\nПоддомены для {domain}:")
    if subdomains:
        for subdomain in subdomains:
            print(subdomain)
    else:
        print("Не удалось найти поддомены.")

for domain, cidr_ranges in all_cidr.items():
    print(f"\nCIDR-диапазоны для {domain}:")
    if cidr_ranges:
        for cidr in cidr_ranges:
            print(cidr)
    else:
        print("Не удалось найти CIDR-диапазоны.")