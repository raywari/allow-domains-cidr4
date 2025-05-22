# Читаем домены из файла в JSON-массив
    domains=$(jq -R . < 1.lst | jq -s .)

    # Читаем cidr из файла в JSON-массив
    cidrs=$(jq -R . < 2.lst | jq -s .)

    # Генерируем итоговый JSON
    jq -n --argjson domains "$domains" --argjson cidrs "$cidrs" '
    {
      id: 222222223,
      name: "routing",
      rules: [
        {
          actionType: "hijack-dns",
          invert: false,
          ip_is_private: false,
          ip_version: "",
          name: "rule_1",
          network: "",
          noDrop: false,
          outboundID: -2,
          override_address: "",
          override_port: 0,
          protocol: "dns",
          rejectMethod: "",
          simple_action: 0,
          sniffOverrideDest: false,
          source_ip_is_private: false,
          strategy: "",
          type: 0
        },
        {
          actionType: "route",
          domain_suffix: $domains,
          invert: false,
          ip_is_private: false,
          ip_version: "",
          name: "rule_2",
          network: "",
          noDrop: false,
          outboundID: -1,
          override_address: "",
          override_port: 0,
          protocol: "",
          rejectMethod: "",
          simple_action: 0,
          sniffOverrideDest: false,
          source_ip_is_private: false,
          strategy: "",
          type: 0
        },
        {
          actionType: "route",
          ip_cidr: $cidrs,
          invert: false,
          ip_is_private: false,
          ip_version: "",
          name: "rule_3",
          network: "",
          noDrop: false,
          outboundID: -1,
          override_address: "",
          override_port: 0,
          protocol: "",
          rejectMethod: "",
          simple_action: 1600940404,
          sniffOverrideDest: false,
          source_ip_is_private: false,
          strategy: "",
          type: 0
        },
        {
          actionType: "route",
          invert: false,
          ip_is_private: false,
          ip_version: "",
          name: "rule_4",
          network: "",
          noDrop: false,
          outboundID: -2,
          override_address: "",
          override_port: 0,
          process_name: ["Discord.exe"],
          protocol: "",
          rejectMethod: "",
          simple_action: 0,
          sniffOverrideDest: false,
          source_ip_is_private: false,
          strategy: "",
          type: 0
        }
      ]
    }' > mahdi.json
