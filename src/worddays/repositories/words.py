"""Запросы к таблице words."""
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import User, UserWord, Word


async def next_unseen(session: AsyncSession, user: User, limit: int) -> list[Word]:
    """Следующие `limit` слов, которые пользователю ещё не выдавались.

    Порядок - от простого к сложному: уровень (A1 -> C1), внутри уровня слова любимой
    темы идут первыми, затем по частотности (freq_rank по возрастанию).
    Слова ниже уровня пользователя пропускаются.
    """
    seen = select(UserWord.word_id).where(UserWord.user_id == user.id)
    order = [Word.level]
    if user.theme:
        order.append(case((Word.theme == user.theme, 0), else_=1))
    order += [Word.freq_rank, Word.id]

    stmt = (
        select(Word)
        .where(Word.is_active.is_(True), Word.level >= user.level, Word.id.not_in(seen))
        .order_by(*order)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def by_ids(session: AsyncSession, ids: list[int]) -> list[Word]:
    """Слова по списку id, в том же порядке, что и в `ids`."""
    if not ids:
        return []
    rows = (await session.execute(select(Word).where(Word.id.in_(ids)))).scalars()
    position = {word_id: i for i, word_id in enumerate(ids)}
    return sorted(rows, key=lambda w: position[w.id])


async def random_others(session: AsyncSession, word: Word, limit: int = 20) -> list[Word]:
    """Случайные другие слова для вариантов-ловушек; слова того же уровня идут первыми."""
    stmt = (
        select(Word)
        .where(Word.id != word.id, Word.is_active.is_(True))
        .order_by(case((Word.level == word.level, 0), else_=1), func.random())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())
