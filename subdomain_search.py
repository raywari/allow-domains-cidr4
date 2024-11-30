import sublist3r

# Функция для поиска поддоменов с брутфорсом
def find_subdomains(domain):
    # Включаем брутфорс, указываем поисковые системы, отключаем цветной вывод
    subdomains = sublist3r.main(domain, savefile=None, ports=None, silent=False, verbose=True, enable_bruteforce=True, engines=['google', 'bing', 'yahoo'])
    return subdomains

# Ввод домена
domain = 'github.com'

# Поиск поддоменов
subdomains = find_subdomains(domain)

# Вывод результатов
print(f"Поддомены для {domain}:")
for subdomain in subdomains:
    print(subdomain)