import type { CommandOption } from "../types/netpanel";

export const commandOptions: CommandOption[] = [
  { value: "running_config", label: "Скопировать running-config", description: "show running-config" },
  { value: "arp_table", label: "Скопировать ARP-таблицу", description: "show ip arp" },
  { value: "mac_on_interface", label: "Найти MAC на интерфейсе", description: "MAC lookup и проверка порта" },
  { value: "routing_table", label: "Таблица BGP / OSPF", description: "Маршруты и базовая сводка" },
  { value: "protocol_neighbors", label: "Соседи BGP / OSPF", description: "Соседства протоколов маршрутизации" },
  { value: "static_routes", label: "Статические маршруты", description: "show ip route static" },
  { value: "route_lookup", label: "Поиск адреса или диапазона", description: "Проверка существования маршрута" },
  { value: "discovery_neighbors", label: "Соседи CDP / LLDP", description: "Топология, имена, платформы и порты" },
  { value: "interface_diagnostics", label: "Статус интерфейсов", description: "Состояние, ошибки, загрузка и пропускная способность" },
  { value: "ip_interface_brief", label: "IP-интерфейсы", description: "Краткая сводка адресов и состояния интерфейсов" },
  { value: "mac_table", label: "Таблица MAC-адресов", description: "CAM-таблица с поиском по MAC или VLAN" },
  { value: "ip_location", label: "Найти устройство по IP", description: "ARP, DHCP Snooping и IP Device Tracking" },
  { value: "reachability", label: "Ping / Traceroute", description: "Проверка доступности с устройства" },
  { value: "system_monitoring", label: "Система и мониторинг", description: "Версия, uptime, CPU, память и питание" },
  { value: "logs", label: "Просмотр логов", description: "show logging с фильтром и лимитом строк" },
];
