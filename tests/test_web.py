import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.config import Settings
from worddays.db.base import Base
from worddays.db.models import Bonus, BonusReason, Level, User, Word
from worddays.web.app import create_app

H = {"X-Requested-With": "wordday"}  # заголовок, который добавляет интерфейс
PASSWORD = "correct horse battery"
HEADER = "word,transcription,translation_ru,translation_uz,example,theme,level,freq_rank,audio_file"
WORD = {"word": "Banana", "transcription": "bəˈnɑːnə", "translation_ru": "банан",
        "translation_uz": "banan", "example": "I eat a banana.", "theme": "food", "level": "A1"}


def make_settings(tmp_path, password=PASSWORD):
    return Settings(
        _env_file=None, bot_token="1:x", admin_id=1, database_url="sqlite+aiosqlite://",
        web_admin_password=password, web_secret_key="k" * 32, audio_dir=tmp_path / "audio",
        web_dist_dir=tmp_path / "no-dist",
    )


@pytest.fixture
async def env(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    bot = MagicMock()
    bot.send_message = AsyncMock()
    settings = make_settings(tmp_path)
    app = create_app(settings, factory, bot)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://test") as client:
        yield type("Env", (), {"client": client, "factory": factory, "bot": bot, "app": app,
                               "settings": settings})
    await engine.dispose()


async def login(env):
    r = await env.client.post("/api/login", json={"password": PASSWORD})
    assert r.status_code == 200
    return env.client


# ---------- доступ ----------

PROTECTED = [("GET", "/api/dashboard"), ("GET", "/api/words"), ("GET", "/api/words/meta"),
             ("GET", "/api/bonuses"), ("GET", "/api/settings"), ("GET", "/api/users"),
             ("GET", "/api/broadcast"), ("GET", "/api/me"), ("POST", "/api/words"),
             ("PUT", "/api/settings"), ("POST", "/api/bonuses/1/pay"),
             ("POST", "/api/users/1/block"), ("POST", "/api/broadcast")]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
async def test_everything_requires_login(env, method, path):
    r = await env.client.request(method, path, headers=H, json={})
    assert r.status_code == 401


async def test_app_refuses_to_start_without_password(tmp_path):
    with pytest.raises(RuntimeError, match="WEB_ADMIN_PASSWORD"):
        create_app(make_settings(tmp_path, password=None), MagicMock(), MagicMock())


async def test_wrong_password_and_lockout(env):
    for _ in range(5):
        r = await env.client.post("/api/login", json={"password": "nope"})
        assert r.status_code == 401
    r = await env.client.post("/api/login", json={"password": PASSWORD})
    assert r.status_code == 429  # даже верный пароль после серии неудач блокируется


async def test_login_sets_httponly_strict_cookie(env):
    r = await env.client.post("/api/login", json={"password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert (await env.client.get("/api/me")).status_code == 200


async def test_logout_ends_session(env):
    c = await login(env)
    await c.post("/api/logout", headers=H)
    assert (await c.get("/api/me")).status_code == 401


async def test_changing_password_invalidates_old_sessions(env, tmp_path):
    c = await login(env)
    new_app = create_app(make_settings(tmp_path, password="a different password"),
                         env.factory, env.bot)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=new_app),
                                 base_url="http://test", cookies=c.cookies) as other:
        assert (await other.get("/api/me")).status_code == 401


async def test_tampered_cookie_rejected(env):
    env.client.cookies.set("wd_session", "forged.value.here")
    assert (await env.client.get("/api/me")).status_code == 401


async def test_state_changing_requests_need_csrf_header(env):
    c = await login(env)
    assert (await c.post("/api/words", json=WORD)).status_code == 403
    assert (await c.post("/api/words", json=WORD, headers=H)).status_code == 201


# ---------- словарь ----------

async def test_words_crud_flow(env):
    c = await login(env)
    r = await c.post("/api/words", json=WORD, headers=H)
    w = r.json()
    assert (w["word"], w["transcription"], w["freq_rank"], w["level"]) == (
        "banana", "/bəˈnɑːnə/", 1, "A1")
    assert w["is_active"] and not w["has_audio"] and w["example_has_word"]

    assert (await c.post("/api/words", json=WORD, headers=H)).status_code == 409  # дубль

    upd = await c.put(f"/api/words/{w['id']}", headers=H,
                      json={**WORD, "translation_ru": "бананы", "level": "B1", "freq_rank": 7})
    assert upd.status_code == 200 and upd.json()["translation_ru"] == "бананы"
    assert (upd.json()["level"], upd.json()["freq_rank"]) == ("B1", 7)

    off = await c.post(f"/api/words/{w['id']}/toggle", headers=H)
    assert off.json()["is_active"] is False
    assert (await c.get("/api/words", params={"active": "true"})).json()["total"] == 0
    assert (await c.get("/api/words", params={"active": "false"})).json()["total"] == 1
    assert (await c.get("/api/words/999")).status_code == 404


@pytest.mark.parametrize("patch", [
    {"word": "кот"}, {"word": "a" * 65}, {"translation_ru": ""}, {"level": "Z9"},
    {"theme": "Bad Theme!"}, {"freq_rank": 0}, {"example": "x" * 301},
])
async def test_word_validation(env, patch):
    c = await login(env)
    r = await c.post("/api/words", json={**WORD, **patch}, headers=H)
    assert r.status_code == 422


async def test_rename_to_existing_word_conflicts(env):
    c = await login(env)
    await c.post("/api/words", json=WORD, headers=H)
    other = (await c.post("/api/words", json={**WORD, "word": "apple"}, headers=H)).json()
    r = await c.put(f"/api/words/{other['id']}", json={**WORD, "word": "banana"}, headers=H)
    assert r.status_code == 409


async def test_list_filters_search_and_pagination(env):
    c = await login(env)
    for i, (name, lvl, theme) in enumerate([("apple", "A1", "food"), ("book", "A1", "school"),
                                            ("cat", "A2", "nature"), ("dog", "A2", "nature")]):
        await c.post("/api/words", headers=H,
                     json={**WORD, "word": name, "level": lvl, "theme": theme,
                           "translation_ru": f"слово{i}"})
    assert (await c.get("/api/words")).json()["total"] == 4
    assert (await c.get("/api/words", params={"level": "A2"})).json()["total"] == 2
    assert (await c.get("/api/words", params={"theme": "nature"})).json()["total"] == 2
    assert [w["word"] for w in (await c.get("/api/words", params={"q": "ca"})).json()["items"]] \
        == ["cat"]
    page = (await c.get("/api/words", params={"size": 3, "page": 2})).json()
    assert page["total"] == 4 and [w["word"] for w in page["items"]] == ["dog"]
    assert (await c.get("/api/words", params={"size": 1000})).status_code == 422
    order = [w["word"] for w in (await c.get("/api/words")).json()["items"]]
    assert order == ["apple", "book", "cat", "dog"]  # уровень, затем место на уровне


async def test_meta(env):
    c = await login(env)
    meta = (await c.get("/api/words/meta")).json()
    assert meta["levels"] == ["A1", "A2", "B1", "B2", "C1"] and "food" in meta["themes"]


async def test_csv_import_and_errors(env):
    c = await login(env)
    good = f"{HEADER}\nsun,/sʌn/,солнце,quyosh,The sun is hot.,nature,A1,1,\n"
    r = await c.post("/api/words/import", headers=H, files={"file": ("w.csv", good.encode())})
    assert r.json() == {"new": 1, "updated": 0, "missing_audio": 0}
    r = await c.post("/api/words/import", headers=H, files={"file": ("w.csv", good.encode())})
    assert r.json()["updated"] == 1

    bad = f"{HEADER}\nsun,/s/,,,E.,n,Z9,1,\n"
    r = await c.post("/api/words/import", headers=H, files={"file": ("w.csv", bad.encode())})
    assert r.status_code == 422
    r = await c.post("/api/words/import", headers=H, files={"file": ("w.txt", b"x")})
    assert r.status_code == 422
    r = await c.post("/api/words/import", headers=H,
                     files={"file": ("w.csv", b"\xff\xfe\x00bad")})
    assert r.status_code == 422


async def test_audio_upload_download_and_validation(env):
    c = await login(env)
    w = (await c.post("/api/words", json=WORD, headers=H)).json()
    mp3 = b"ID3\x03\x00\x00\x00" + b"\x00" * 64

    assert (await c.get(f"/api/words/{w['id']}/audio")).status_code == 404  # озвучки нет
    r = await c.post(f"/api/words/{w['id']}/audio", headers=H,
                     files={"file": ("banana.mp3", mp3, "audio/mpeg")})
    assert r.status_code == 200 and r.json()["has_audio"]
    got = await c.get(f"/api/words/{w['id']}/audio")
    assert got.status_code == 200 and got.content == mp3
    assert got.headers["content-type"] == "audio/mpeg"
    assert (env.settings.audio_dir / "banana.mp3").read_bytes() == mp3

    for name, data in [("x.wav", mp3), ("x.mp3", b"not audio at all"),
                       ("x.mp3", b"ID3" + b"\x00" * (5 * 1024 * 1024))]:
        r = await c.post(f"/api/words/{w['id']}/audio", headers=H, files={"file": (name, data)})
        assert r.status_code in (413, 422), name


async def test_audio_path_cannot_escape_audio_dir(env, tmp_path):
    c = await login(env)
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    async with env.factory() as s:
        s.add(Word(word="evil", transcription="/x/", translation_ru="x", example="e",
                   theme="basic", level=Level.A1, freq_rank=1, audio_path="../secret.txt"))
        await s.commit()
    r = await c.get("/api/words/1/audio")
    assert r.status_code == 404 and b"top secret" not in r.content


# ---------- бонусы ----------

async def seed_bonus(env, tg=10, amount=5000):
    async with env.factory() as s:
        user = User(telegram_id=tg, username=f"u{tg}", phone=f"+99890{tg:07d}", is_onboarded=True)
        s.add(user)
        await s.commit()
        bonus = Bonus(user_id=user.id, reason=BonusReason.TOP_WEEK, amount=amount,
                      week=date(2026, 10, 26))
        s.add(bonus)
        await s.commit()
        return bonus.id


async def test_bonus_queue_pay_and_reject(env):
    c = await login(env)
    first, second = await seed_bonus(env, 10), await seed_bonus(env, 11, 3000)
    queue = (await c.get("/api/bonuses")).json()
    assert [b["id"] for b in queue] == [first, second]
    assert queue[0]["phone"] and queue[0]["flags_block"] == [] and queue[0]["test_passed"] is False
    assert (await c.get("/api/bonuses/counts")).json()["pending"] == 2

    paid = await c.post(f"/api/bonuses/{first}/pay", headers=H)
    assert paid.status_code == 200 and paid.json()["status"] == "paid"
    env.bot.send_message.assert_awaited_once()  # ученик уведомлён
    assert env.bot.send_message.await_args.args[0] == 10

    assert (await c.post(f"/api/bonuses/{first}/pay", headers=H)).status_code == 409  # повтор
    rej = await c.post(f"/api/bonuses/{second}/reject", headers=H)
    assert rej.json()["status"] == "rejected"
    assert env.bot.send_message.await_count == 1  # об отказе не уведомляем
    assert (await c.get("/api/bonuses")).json() == []
    assert len((await c.get("/api/bonuses", params={"status": "paid"})).json()) == 1


# ---------- настройки ----------

async def test_settings_roundtrip_and_limits(env):
    c = await login(env)
    cur = (await c.get("/api/settings")).json()
    assert cur["words_per_day"] == 10 and cur["limits"]["top_n"] == [1, 5]
    new = {"words_per_day": 12, "top_n": 4, "weekly_budget": 60000, "monthly_budget": 240000}
    r = await c.put("/api/settings", json=new, headers=H)
    assert {k: r.json()[k] for k in new} == new
    for bad in ({"words_per_day": 0}, {"words_per_day": 31}, {"top_n": 6}, {"weekly_budget": -1}):
        assert (await c.put("/api/settings", json={**new, **bad}, headers=H)).status_code == 422
    assert (await c.get("/api/settings")).json()["words_per_day"] == 12  # не испорчено


# ---------- ученики ----------

async def test_users_search_and_block(env):
    c = await login(env)
    await seed_bonus(env, 10)
    await seed_bonus(env, 11)
    assert (await c.get("/api/users")).json()["total"] == 2
    assert (await c.get("/api/users", params={"q": "@u10"})).json()["total"] == 1
    assert (await c.get("/api/users", params={"q": "11"})).json()["total"] >= 1  # id или телефон

    uid = (await c.get("/api/users", params={"q": "u10"})).json()["items"][0]["id"]
    r = await c.post(f"/api/users/{uid}/block", json={"blocked": True}, headers=H)
    assert r.json()["is_blocked"] is True
    assert (await c.get("/api/users", params={"blocked": "true"})).json()["total"] == 1
    assert (await c.post("/api/users/9999/block", json={"blocked": True}, headers=H)).status_code == 404


# ---------- дашборд и рассылка ----------

async def test_dashboard_shape(env):
    c = await login(env)
    d = (await c.get("/api/dashboard")).json()
    assert {"overview", "activity", "levels", "budget_used"} <= d.keys()
    assert len(d["activity"]) == 14 and len(d["levels"]) == 5
    assert d["overview"]["users"] == 0


async def test_broadcast_sends_to_active_users_only(env):
    c = await login(env)
    await seed_bonus(env, 10)
    await seed_bonus(env, 11)
    async with env.factory() as s:
        banned = User(telegram_id=12, is_onboarded=True, is_blocked=True)
        s.add(banned)
        await s.commit()

    status = (await c.get("/api/broadcast")).json()
    assert status["audience"] == 2 and status["running"] is False

    r = await c.post("/api/broadcast", json={"text": "Привет <b>всем</b>!"}, headers=H)
    assert r.status_code == 202 and r.json()["total"] == 2
    for _ in range(50):
        if not (await c.get("/api/broadcast")).json()["running"]:
            break
        await asyncio.sleep(0.05)
    final = (await c.get("/api/broadcast")).json()
    assert final["sent"] == 2 and final["failed"] == 0
    assert {call.args[0] for call in env.bot.send_message.await_args_list} == {10, 11}
    assert "&lt;b&gt;" in env.bot.send_message.await_args.args[1]  # HTML экранирован

    assert (await c.post("/api/broadcast", json={"text": "  "}, headers=H)).status_code == 422


async def test_pay_survives_telegram_failure(env):
    """Сбой отправки уведомления не отменяет решение админа."""
    c = await login(env)
    bonus_id = await seed_bonus(env, 10)
    env.bot.send_message.side_effect = RuntimeError("telegram is down")
    r = await c.post(f"/api/bonuses/{bonus_id}/pay", headers=H)
    assert r.status_code == 200
    assert r.json()["status"] == "paid" and r.json()["notified"] is False
    assert (await c.get("/api/bonuses/counts")).json() == {"pending": 0, "paid": 1, "rejected": 0}


async def test_panel_starts_without_valid_token_and_reports_send_failures(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = make_settings(tmp_path)
    settings.bot_token = "PUT_YOUR_TOKEN_HERE"  # заглушка из шаблона .env
    app = create_app(settings, factory)  # не падает
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://test") as client:
        assert (await client.post("/api/login", json={"password": PASSWORD})).status_code == 200
        assert (await client.get("/api/dashboard")).status_code == 200
        async with factory() as s:
            user = User(telegram_id=5, is_onboarded=True)
            s.add(user)
            await s.commit()
            s.add(Bonus(user_id=user.id, reason=BonusReason.TOP_WEEK, amount=3000,
                        week=date(2026, 10, 26)))
            await s.commit()
        paid = await client.post("/api/bonuses/1/pay", headers=H)
        assert paid.status_code == 200 and paid.json()["notified"] is False
    await engine.dispose()
