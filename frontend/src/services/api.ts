export async function parseResponse(response: Response) {
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(data.detail || response.statusText);
  return data;
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Неизвестная ошибка";
}
