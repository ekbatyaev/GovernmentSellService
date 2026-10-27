import { ApiError } from "../api/client";

// Тексты ошибок бэка (detail из HTTPException) → понятные пользователю сообщения.
const KNOWN_ERRORS: Record<string, string> = {
  "Invalid email or password": "Неверный email или пароль",
  "Invalid token": "Сессия истекла, войдите снова",
  "User already exists": "Пользователь с таким email уже зарегистрирован",
  "Not found": "Код не найден, запросите новый",
  "Not found auth code": "Код не найден, запросите новый",
  "The code is expired": "Срок действия кода истёк, запросите новый",
  "Too many attempts, try again later": "Слишком частые попытки — подождите 20 секунд",
  "Invalid code": "Неверный код",
  "Code not saved": "Не удалось сохранить код, попробуйте ещё раз",
  "The code is not deleted": "Не удалось завершить проверку кода, попробуйте ещё раз",
  "Failed to create newsletter": "Вы уже подписаны на эту рассылку",
  "Admin only": "Действие доступно только администратору",
  "User is not exists": "Пользователь не найден",
  "Purchase not found": "Заявка не найдена",
  "The mail server is not available right now. Please, try later.":
    "Почтовый сервер недоступен, попробуйте позже",
};

export function errorMessage(error: unknown, fallback = "Ошибка"): string {
  if (error instanceof ApiError) return KNOWN_ERRORS[error.message] ?? error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}
