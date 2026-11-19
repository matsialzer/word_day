"""Вход в веб-панель: пароль из .env, подписанная cookie-сессия, защита от перебора."""
import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

COOKIE = "wd_session"
SESSION_TTL = 8 * 3600  # сессия живёт 8 часов
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "wordday"  # интерфейс добавляет заголовок ко всем запросам на изменение

MAX_FAILS = 5
FAIL_WINDOW = 15 * 60  # после 5 неверных паролей за 15 минут вход блокируется


def password_fingerprint(password: str) -> str:
    """Отпечаток пароля внутри сессии: смена пароля в .env разлогинивает всех."""
    return hashlib.sha256(password.encode()).hexdigest()[:16]


def check_password(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode(), expected.encode())


class LoginGuard:
    """Ограничение числа неудачных попыток входа с одного адреса (в памяти процесса)."""

    def __init__(self) -> None:
        self._fails: dict[str, deque[float]] = defaultdict(deque)

    def _recent(self, ip: str) -> deque[float]:
        fails = self._fails[ip]
        cutoff = time.monotonic() - FAIL_WINDOW
        while fails and fails[0] < cutoff:
            fails.popleft()
        return fails

    def is_blocked(self, ip: str) -> bool:
        return len(self._recent(ip)) >= MAX_FAILS

    def record_fail(self, ip: str) -> None:
        self._recent(ip).append(time.monotonic())

    def reset(self, ip: str) -> None:
        self._fails.pop(ip, None)


def make_serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="wordday-admin-session")


def require_admin(request: Request) -> None:
    """Зависимость всех закрытых маршрутов: действительная сессия + защита от CSRF."""
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Требуется вход")
    try:
        payload = request.app.state.serializer.loads(token, max_age=SESSION_TTL)
    except BadSignature:  # включая истёкшую подпись
        raise HTTPException(401, "Сессия недействительна") from None
    expected = password_fingerprint(request.app.state.settings.web_admin_password)
    if payload.get("fp") != expected:
        raise HTTPException(401, "Сессия недействительна")

    # SameSite=Strict уже защищает cookie; заголовок - вторая линия обороны от CSRF
    if request.method not in {"GET", "HEAD", "OPTIONS"} \
            and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(403, "Запрос отклонён")
