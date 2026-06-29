import type { ResultMetric } from "../types/netpanel";

export function statusLabel(value: string) {
  return ({
    connected: "Подключён",
    notconnect: "Нет подключения",
    disabled: "Отключён",
    "err-disabled": "Ошибка",
    inactive: "Неактивен",
  } as Record<string, string>)[value.toLowerCase()] || value;
}

export function ipInterfaceStatusLabel(value: string) {
  return ({
    up: "Включён",
    down: "Нет соединения",
    "administratively down": "Выключен администратором",
  } as Record<string, string>)[value.toLowerCase()] || value;
}

export function ipMethodLabel(value: string) {
  return ({
    manual: "Статический",
    nvram: "Из конфигурации",
    dhcp: "DHCP",
    unset: "Не задан",
  } as Record<string, string>)[value.toLowerCase()] || value;
}

export function formatRate(value: number) {
  if (!value) return "0 бит/с";
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)} Гбит/с`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)} Мбит/с`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)} Кбит/с`;
  return `${value} бит/с`;
}

export function speedLabel(value: string) {
  const normalized = String(value || "").trim().toLowerCase();
  const automatic = normalized.startsWith("a-");
  const speed = normalized.replace(/^a-/, "").replace(/^-/, "");
  if (speed === "auto") return "Auto";
  if (/^\d+$/.test(speed)) {
    const numeric = Number(speed);
    const label = numeric >= 1000 ? `${numeric / 1000} Гбит/с` : `${numeric} Мбит/с`;
    return automatic ? `${label} (auto)` : label;
  }
  return value || "—";
}

export function duplexLabel(value: string) {
  return ({
    full: "Full",
    half: "Half",
    "a-full": "Full (auto)",
    "a-half": "Half (auto)",
    auto: "Auto",
  } as Record<string, string>)[value.toLowerCase()] || value || "—";
}

export function metricValue(metric: ResultMetric) {
  const value = Number(metric.value);
  if (metric.label === "Пропускная способность") return formatRate(value * 1000);
  if (metric.label.includes("трафик")) return formatRate(value);
  if (metric.label.includes("пакеты")) return `${value} пак/с`;
  if (metric.label === "MTU") return `${value} байт`;
  if (metric.label === "Задержка") return `${value} мкс`;
  if (metric.label === "Надёжность" || metric.label.includes("Загрузка")) {
    const [current, maximum] = metric.value.split("/").map(Number);
    if (maximum) return `${Math.round((current / maximum) * 100)}%`;
  }
  return metric.value;
}
