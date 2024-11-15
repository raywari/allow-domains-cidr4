#!/bin/dash
INPUT_FILE="domains.lst"
OUTPUT_FILE="domains.json"
OUTPUT_SRS_FILE="domains.srs"

echo "Удаление старых файлов..."
rm -f "$INPUT_FILE" "$OUTPUT_FILE" "$OUTPUT_SRS_FILE"

echo "Скачивание списка доменов..."
URL="https://raw.githubusercontent.com/raywari/allow-domains-cidr4/refs/heads/main/domains.lst?$(date +%s)"
wget -q -O "$INPUT_FILE" "$URL"
if [ $? -ne 0 ]; then
    echo "Ошибка при скачивании файла с доменами!"
    exit 1
fi

domain_list=""
domain_suffix_list=""

while read -r domain; do
    if echo "$domain" | grep -Eq '^[^.]+\.[^.]+$'; then
        domain_list="$domain_list\"$domain\","
    else
        domain_suffix_list="$domain_suffix_list\"$domain\","
    fi
done < "$INPUT_FILE"

domain_list=$(echo "$domain_list" | sed 's/,$//')
domain_suffix_list=$(echo "$domain_suffix_list" | sed 's/,$//')

echo "Создание JSON файла с правилами..."
cat <<EOF > "$OUTPUT_FILE"
{
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
  ],
  "version": 2
}
EOF

echo "JSON файл с правилами:"
cat "$OUTPUT_FILE"

echo "Компиляция в SRS файл..."
sing-box rule-set compile "$OUTPUT_FILE" -o "$OUTPUT_SRS_FILE"
if [ $? -ne 0 ]; then
    echo "Ошибка при компиляции .srs файла!"
    exit 1
fi

echo "Файл $OUTPUT_SRS_FILE успешно создан!"
