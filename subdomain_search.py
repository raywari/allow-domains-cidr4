import sublist3r

# Функция для поиска поддоменов с брутфорсом
def find_subdomains(domain):
    # Включаем брутфорс и указываем поисковые системы
    subdomains = sublist3r.main(domain, 40, None, True, ['google', 'bing', 'yahoo'], False)
    return subdomains

# Ввод домена
domain = 'github.com'

# Поиск поддоменов
subdomains = find_subdomains(domain)

# Вывод результатов
print(f"Поддомены для {domain}:")
for subdomain in subdomains:
    print(subdomain)