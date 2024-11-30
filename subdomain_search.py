import sublist3r

# Функция для поиска поддоменов
def find_subdomains(domain):
    # Используем sublist3r для поиска поддоменов с максимально возможным количеством потоков
    subdomains = sublist3r.main(domain, 40, None, True, True, False)
    return subdomains

# Ввод домена
domain = 'github.com'

# Поиск поддоменов
subdomains = find_subdomains(domain)

# Вывод результатов
print(f"Поддомены для {domain}:")
for subdomain in subdomains:
    print(subdomain)