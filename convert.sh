#!/bin/dash

# Файл с доменами
INPUT_FILE="domains.lst"
OUTPUT_FILE="domains.json"
OUTPUT_SRS_FILE="domains.srs"

# Удаляем старые файлы, если они существуют
echo "Удаление старых файлов..."
rm -f "$INPUT_FILE" "$OUTPUT_FILE" "$OUTPUT_SRS_FILE"

# URL для скачивания списка доменов
URL="https://raw.githubusercontent.com/raywari/allow-domains-cidr4/refs/heads/main/domains.lst"

# Скачиваем файл с доменами
echo "Скачивание списка доменов..."
curl -s -o "$INPUT_FILE" "$URL"
if [ $? -ne 0 ]; then
    echo "Ошибка при скачивании файла с доменами!"
    exit 1
fi

# Переменные для хранения доменов второго и третьего уровня
domain_list=""
domain_suffix_list=""

# Читаем файл и распределяем домены
while read -r domain; do
    # Проверка на второй или третий уровень
    if echo "$domain" | grep -Eq '^[^.]+\.[^.]+$'; then
        # Если домен второго уровня (например, russia.org)
        domain_list="$domain_list\"$domain\","
    else
        # Если домен третьего уровня (например, free.russia.org)
        domain_suffix_list="$domain_suffix_list\"$domain\","
    fi
done < "$INPUT_FILE"

# Убираем последнюю запятую
domain_list=$(echo "$domain_list" | sed 's/,$//')
domain_suffix_list=$(echo "$domain_suffix_list" | sed 's/,$//')

# Собираем JSON
echo "Создание JSON файла с правилами..."
cat <<EOF > "$OUTPUT_FILE"
{
  "version": 2,
  "rules": [
    {
      "domain": [
        $domain_list
      ]
    },
    {
      "domain_suffix": [
        $domain_suffix_list
      ]
    }
  ]
}
EOF

# Выводим результат JSON в консоль
echo "JSON файл с правилами:"
cat "$OUTPUT_FILE"

# Компиляция в .srs с использованием sing-box
echo "Компиляция в SRS файл..."
sing-box rule-set compile "$OUTPUT_FILE" -o "$OUTPUT_SRS_FILE"
if [ $? -ne 0 ]; then
    echo "Ошибка при компиляции .srs файла!"
    exit 1
fi

echo "Файл $OUTPUT_SRS_FILE успешно создан!"
