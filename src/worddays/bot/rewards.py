"""Тексты наград (XP, серия, уровень, достижения) для сообщений бота."""
from worddays.bot.texts import t
from worddays.db.models import Language
from worddays.services.gamification import Reward


def reward_lines(lang: Language, reward: Reward) -> list[str]:
    lines: list[str] = []
    if reward.xp:
        lines.append(t(lang, "reward_xp", xp=reward.xp))
    if reward.capped:
        lines.append(t(lang, "reward_xp_capped"))
    if reward.streak is not None:
        lines.append(t(lang, "reward_streak", n=reward.streak))
    if reward.freezes_used:
        lines.append(t(lang, "reward_freeze_used", n=reward.freezes_used))
    if reward.freeze_earned:
        lines.append(t(lang, "reward_freeze_earned"))
    if reward.level_up:
        lines.append(t(lang, "reward_level_up", level=reward.level_up.value))
    for code in reward.badges:
        lines.append(t(lang, "badge_new", name=t(lang, f"badge_{code}")))
    return lines
