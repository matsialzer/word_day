"""Стенд для сквозных тестов: настоящий Dispatcher + роутеры + FSM, подставной Telegram.

Бот не ходит в сеть: все исходящие вызовы перехватываются и складываются в `fake.calls`.
"""
import itertools
from datetime import UTC, datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import (
    Audio,
    CallbackQuery,
    Chat,
    Contact,
    Message,
    PhotoSize,
    Update,
)
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.bot.handlers import all_routers
from worddays.bot.middlewares.db import DbSessionMiddleware
from worddays.db.base import Base

_ids = itertools.count(1)


class FakeTelegram:
    """Перехватывает вызовы Bot API и отвечает «успехом»."""

    def __init__(self) -> None:
        self.calls: list = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        name = type(method).__name__
        chat_id = getattr(method, "chat_id", 0) or 0
        if name in {"SendMessage", "EditMessageText", "SendAudio", "SendPhoto",
                    "EditMessageReplyMarkup"}:
            return Message(
                message_id=next(_ids), date=datetime.now(UTC),
                chat=Chat(id=chat_id, type="private"), text=getattr(method, "text", None),
                audio=Audio(file_id="FID", file_unique_id="u", duration=1)
                if name == "SendAudio" else None,
                photo=[PhotoSize(file_id="PID", file_unique_id="p", width=1, height=1)]
                if name == "SendPhoto" else None,
            )
        return True

    def sent(self, kind: str = "SendMessage") -> list:
        return [c for c in self.calls if type(c).__name__ == kind]

    def texts(self, chat_id: int | None = None) -> list[str]:
        out = []
        for c in self.calls:
            is_text = type(c).__name__ in {"SendMessage", "EditMessageText"}
            if is_text and (chat_id is None or getattr(c, "chat_id", chat_id) == chat_id):
                out.append(c.text)
        return out

    def last_markup(self):
        for c in reversed(self.calls):
            markup = getattr(c, "reply_markup", None)
            if markup is not None:
                return markup
        return None


class Harness:
    def __init__(self, engine, bot: Bot, dp: Dispatcher, fake: FakeTelegram, factory) -> None:
        self.engine, self.bot, self.dp, self.fake, self.factory = engine, bot, dp, fake, factory

    # ----- входящие апдейты -----
    def _user(self, uid: int) -> TgUser:
        return TgUser(id=uid, is_bot=False, first_name="Tester", username=f"user{uid}")

    def _message(self, uid: int, **kw) -> Message:
        return Message(message_id=next(_ids), date=datetime.now(UTC),
                       chat=Chat(id=uid, type="private"), from_user=self._user(uid), **kw)

    async def send(self, uid: int, text: str) -> None:
        await self.dp.feed_update(self.bot, Update(update_id=next(_ids),
                                                   message=self._message(uid, text=text)))

    async def send_contact(self, uid: int, phone: str, contact_uid: int | None = None) -> None:
        contact = Contact(phone_number=phone, first_name="T", user_id=contact_uid or uid)
        await self.dp.feed_update(self.bot, Update(update_id=next(_ids),
                                                   message=self._message(uid, contact=contact)))

    async def press(self, uid: int, data: str) -> None:
        cb = CallbackQuery(id=str(next(_ids)), from_user=self._user(uid), chat_instance="ci",
                           data=data, message=self._message(uid, text="menu"))
        await self.dp.feed_update(self.bot, Update(update_id=next(_ids), callback_query=cb))

    # ----- состояние -----
    def key(self, uid: int) -> StorageKey:
        return StorageKey(bot_id=self.bot.id, chat_id=uid, user_id=uid)

    async def fsm_data(self, uid: int) -> dict:
        return await self.dp.storage.get_data(self.key(uid))

    async def fsm_update(self, uid: int, **data) -> None:
        await self.dp.storage.update_data(self.key(uid), data)

    async def fsm_state(self, uid: int) -> str | None:
        return await self.dp.storage.get_state(self.key(uid))

    def session(self):
        return self.factory()

    async def close(self) -> None:
        await self.bot.session.close()
        await self.engine.dispose()


async def make_harness() -> Harness:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    fake = FakeTelegram()
    bot = Bot("123456:TEST")
    bot.session.make_request = fake.make_request  # type: ignore[method-assign]

    dp = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
    dp.update.outer_middleware(DbSessionMiddleware(factory))
    routers = all_routers()
    for router in routers:  # роутеры глобальные; в тестах диспетчер создаётся заново каждый раз
        router._parent_router = None
    dp.include_routers(*routers)
    return Harness(engine, bot, dp, fake, factory)
