import sublist3r

# Функция для поиска поддоменов с брутфорсом
def find_subdomains(domain):
    # Включаем брутфорс, указываем поисковые системы, отключаем цветной вывод
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
    return subdomains

# Ввод домена
domain = 'youtube.com'

# Поиск поддоменов
subdomains = find_subdomains(domain)

# Вывод результатов
print(f"Поддомены для {domain}:")
for subdomain in subdomains:
    print(subdomain)