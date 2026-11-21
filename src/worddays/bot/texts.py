"""Все тексты бота в одном месте: русский и узбекский (латиница).

Использование: t(lang, "key", name=value). Тест tests/test_texts.py следит, чтобы у каждого
ключа были оба перевода и совпадали плейсхолдеры.
"""
from worddays.db.models import Language

TEXTS: dict[str, dict[str, str]] = {
    # --- общее ---
    "choose_language": {
        "ru": "🌐 Выберите язык",
        "uz": "🌐 Tilni tanlang",
    },
    "use_buttons": {
        "ru": "Пожалуйста, выбери вариант кнопкой выше 👆",
        "uz": "Iltimos, yuqoridagi tugmalardan birini tanlang 👆",
    },
    "error_generic": {
        "ru": "😔 Что-то пошло не так. Попробуй ещё раз чуть позже.",
        "uz": "😔 Nimadir xato ketdi. Birozdan so'ng qayta urinib ko'ring.",
    },
    # --- онбординг ---
    "level_prompt": {
        "ru": "Привет! Я WordDay 👋\nКаждый день я присылаю новые английские слова "
              "(по {n} в день) и помогаю их запомнить.\n\nВыбери свой уровень:",
        "uz": "Salom! Men WordDay 👋\nHar kuni yangi inglizcha so'zlar (kuniga {n} tadan) "
              "yuboraman va ularni eslab qolishga yordam beraman.\n\nDarajangizni tanlang:",
    },
    "level_A1": {"ru": "A1 — начинаю с нуля", "uz": "A1 — noldan boshlayman"},
    "level_A2": {"ru": "A2 — базовый", "uz": "A2 — boshlang'ich"},
    "level_B1": {"ru": "B1 — средний", "uz": "B1 — o'rta"},
    "level_B2": {"ru": "B2 — выше среднего", "uz": "B2 — o'rtadan yuqori"},
    "level_C1": {"ru": "C1 — продвинутый", "uz": "C1 — ilg'or"},
    "theme_prompt": {
        "ru": "Какая тема интересует больше всего?",
        "uz": "Qaysi mavzu sizni ko'proq qiziqtiradi?",
    },
    "theme_any": {"ru": "🎲 Любая тема", "uz": "🎲 Istalgan mavzu"},
    "theme_basic": {"ru": "Базовые слова", "uz": "Asosiy so'zlar"},
    "theme_family": {"ru": "Семья и друзья", "uz": "Oila va do'stlar"},
    "theme_food": {"ru": "Еда", "uz": "Ovqat"},
    "theme_home": {"ru": "Дом", "uz": "Uy"},
    "theme_travel": {"ru": "Путешествия", "uz": "Sayohat"},
    "theme_health": {"ru": "Здоровье", "uz": "Salomatlik"},
    "theme_education": {"ru": "Учёба", "uz": "Ta'lim"},
    "theme_nature": {"ru": "Природа", "uz": "Tabiat"},
    "time_prompt": {
        "ru": "В какое время присылать слова дня? Выбери кнопкой или напиши в формате "
              "ЧЧ:ММ (например, 08:30).",
        "uz": "So'zlarni qaysi vaqtda yuboray? Tugma bilan tanlang yoki SS:DD formatida "
              "yozing (masalan, 08:30).",
    },
    "time_invalid": {
        "ru": "Не понял время. Напиши в формате ЧЧ:ММ, например 08:30.",
        "uz": "Vaqtni tushunmadim. SS:DD formatida yozing, masalan 08:30.",
    },
    "tz_prompt": {
        "ru": "Выбери свой часовой пояс кнопкой или напиши его название "
              "(например, Europe/Moscow).",
        "uz": "Vaqt mintaqangizni tugma bilan tanlang yoki nomini yozing "
              "(masalan, Europe/Moscow).",
    },
    "tz_invalid": {
        "ru": "Не знаю такого часового пояса. Пример: Asia/Tashkent.",
        "uz": "Bunday vaqt mintaqasi topilmadi. Masalan: Asia/Tashkent.",
    },
    "phone_prompt": {
        "ru": "Последний шаг: подтверди номер телефона кнопкой ниже.\n"
              "Один номер — один аккаунт. Номер нужен только для защиты бонусов от накрутки "
              "и никому не показывается.",
        "uz": "Oxirgi qadam: telefon raqamingizni pastdagi tugma orqali tasdiqlang.\n"
              "Bitta raqam — bitta akkaunt. Raqam faqat bonuslarni firibgarlikdan himoya qilish "
              "uchun kerak va hech kimga ko'rsatilmaydi.",
    },
    "phone_button": {"ru": "📱 Отправить номер", "uz": "📱 Raqamni yuborish"},
    "phone_not_own": {
        "ru": "Нужно отправить именно свой контакт — нажми кнопку ниже 👇",
        "uz": "Aynan o'zingizning kontaktingizni yuboring — pastdagi tugmani bosing 👇",
    },
    "phone_invalid": {
        "ru": "Не удалось распознать номер. Попробуй ещё раз кнопкой ниже 👇",
        "uz": "Raqamni aniqlab bo'lmadi. Pastdagi tugma orqali qayta urinib ko'ring 👇",
    },
    "phone_taken": {
        "ru": "Этот номер уже привязан к другому аккаунту.",
        "uz": "Bu raqam boshqa akkauntga bog'langan.",
    },
    "phone_remind": {
        "ru": "Нажми кнопку «Отправить номер» ниже 👇",
        "uz": "Pastdagi «Raqamni yuborish» tugmasini bosing 👇",
    },
    "onboarding_done": {
        "ru": "🎉 Готово!\nУровень: {level}\nТема: {theme}\n"
              "Слова дня будут приходить в {time} ({tz}).\n\n"
              "/today — слова дня\n/quiz — викторина\n/stats — статистика\n/help — помощь",
        "uz": "🎉 Tayyor!\nDaraja: {level}\nMavzu: {theme}\n"
              "Kun so'zlari soat {time} da keladi ({tz}).\n\n"
              "/today — kun so'zlari\n/quiz — viktorina\n/stats — statistika\n/help — yordam",
    },
    # --- слова дня ---
    "not_onboarded": {
        "ru": "Сначала быстро настроим бота — отправь /start",
        "uz": "Avval botni sozlab olamiz — /start ni yuboring",
    },
    "lesson_intro": {
        "ru": "📚 Слова дня готовы: {n} шт. Урок займёт пару минут!",
        "uz": "📚 Kun so'zlari tayyor: {n} ta. Dars bir necha daqiqa oladi!",
    },
    "lesson_start": {"ru": "▶️ Начать урок", "uz": "▶️ Darsni boshlash"},
    "lesson_progress": {"ru": "Слово {i} из {n}", "uz": "{i}-so'z / {n}"},
    "lesson_next": {"ru": "Дальше ➡️", "uz": "Keyingi ➡️"},
    "lesson_prev": {"ru": "⬅️ Назад", "uz": "⬅️ Orqaga"},
    "lesson_listen": {"ru": "🔊 Слушать", "uz": "🔊 Tinglash"},
    "lesson_check": {"ru": "🎯 Проверить себя", "uz": "🎯 O'zimni tekshirish"},
    "lesson_stale": {
        "ru": "Этот урок уже неактуален. Откройте /today",
        "uz": "Bu dars eskirgan. /today ni oching",
    },
    "lesson_no_audio": {
        "ru": "Для этого слова пока нет озвучки",
        "uz": "Bu so'z uchun hozircha ovoz yo'q",
    },
    "today_empty": {
        "ru": "🎉 Ты прошёл все доступные слова! Новые появятся совсем скоро.",
        "uz": "🎉 Siz barcha mavjud so'zlarni o'rgandingiz! Yangilari tez orada qo'shiladi.",
    },
    # --- викторина ---
    "q_choice_en_ru": {"ru": "Как переводится слово?", "uz": "So'z qanday tarjima qilinadi?"},
    "q_choice_ru_en": {
        "ru": "Какое английское слово подходит?",
        "uz": "Qaysi inglizcha so'z mos keladi?",
    },
    "q_fill_gap": {
        "ru": "Вставь пропущенное слово:",
        "uz": "Tushib qolgan so'zni qo'ying:",
    },
    "q_picture": {"ru": "🖼 Что на картинке?", "uz": "🖼 Rasmda nima bor?"},
    "q_finish_phrase": {"ru": "Закончи фразу:", "uz": "Iborani tugating:"},
    "q_synonym_antonym_syn": {
        "ru": "🔁 Выбери синоним (близкое по смыслу слово):",
        "uz": "🔁 Sinonimini tanlang (ma'nodosh so'z):",
    },
    "q_synonym_antonym_ant": {
        "ru": "↔️ Выбери антоним (противоположное слово):",
        "uz": "↔️ Antonimini tanlang (qarama-qarshi so'z):",
    },
    "q_match_pairs": {
        "ru": "🧩 Найди пары: нажми слово слева, потом его перевод справа",
        "uz": "🧩 Juftlarni toping: chapdagi so'zni, keyin o'ngdagi tarjimasini bosing",
    },
    "match_pick_first": {
        "ru": "Сначала выбери слово слева", "uz": "Avval chapdagi so'zni tanlang",
    },
    "match_wrong": {"ru": "❌ Это не пара", "uz": "❌ Bu juft emas"},
    "q_listening": {
        "ru": "🎧 Послушай и выбери перевод",
        "uz": "🎧 Tinglang va tarjimasini tanlang",
    },
    "q_build_word": {
        "ru": "Собери слово из букв и напиши его:",
        "uz": "Harflardan so'z tuzing va yozing:",
    },
    "q_write_from_memory": {"ru": "Напиши по-английски:", "uz": "Inglizcha yozing:"},
    "quiz_progress": {"ru": "Вопрос {i}/{n}", "uz": "Savol {i}/{n}"},
    "quiz_type_hint": {
        "ru": "✍️ Напиши ответ сообщением",
        "uz": "✍️ Javobni xabar bilan yozing",
    },
    "quiz_use_buttons": {
        "ru": "Выбери вариант кнопкой под вопросом 👆",
        "uz": "Savol ostidagi tugmalardan birini tanlang 👆",
    },
    "quiz_correct": {"ru": "✅ Верно!", "uz": "✅ To'g'ri!"},
    "quiz_wrong": {
        "ru": "❌ Неверно. Правильный ответ: <b>{answer}</b>",
        "uz": "❌ Noto'g'ri. To'g'ri javob: <b>{answer}</b>",
    },
    "quiz_promoted": {
        "ru": "📈 Следующее повторение через {days} дн.",
        "uz": "📈 Keyingi takrorlash {days} kundan keyin.",
    },
    "quiz_learned": {"ru": "🎓 Слово выучено!", "uz": "🎓 So'z o'zlashtirildi!"},
    "quiz_result": {"ru": "🏁 Результат: {ok}/{n}", "uz": "🏁 Natija: {ok}/{n}"},
    "quiz_none": {
        "ru": "Пока нечего проверять. Получи слова дня: /today",
        "uz": "Hozircha tekshirish uchun so'z yo'q. Kun so'zlari: /today",
    },
    "quiz_stale": {"ru": "Этот вопрос уже неактуален", "uz": "Bu savol eskirgan"},
    "quiz_nudge": {
        "ru": "🎯 Время мини-викторины! Проверим, как запомнились слова.",
        "uz": "🎯 Mini-viktorina vaqti! So'zlar qanchalik eslab qolganini tekshiramiz.",
    },
    "quiz_start_btn": {"ru": "▶️ Начать", "uz": "▶️ Boshlash"},
    # --- недельный тест и бонусы ---
    "weektest_intro": {
        "ru": "📝 Недельный тест: {n} вопросов, нужно не менее {need}% верных.\n"
              "Попытка одна на неделю — удачи!",
        "uz": "📝 Haftalik test: {n} ta savol, kamida {need}% to'g'ri javob kerak.\n"
              "Haftada bitta urinish — omad!",
    },
    "weektest_used": {
        "ru": "Попытка на этой неделе уже использована. Следующий тест — с понедельника.",
        "uz": "Bu haftadagi urinish ishlatilgan. Keyingi test — dushanbadan.",
    },
    "weektest_few": {
        "ru": "Для недельного теста нужно получить хотя бы {min} слов за неделю. "
              "Занимайся по /today!",
        "uz": "Haftalik test uchun hafta davomida kamida {min} ta so'z olish kerak. "
              "/today bo'yicha shug'ullaning!",
    },
    "weektest_passed": {
        "ru": "✅ Недельный тест сдан: {ok}/{n}!",
        "uz": "✅ Haftalik test topshirildi: {ok}/{n}!",
    },
    "weektest_failed": {
        "ru": "❌ Тест не сдан: {ok}/{n}. Новая попытка — со следующей недели.",
        "uz": "❌ Test topshirilmadi: {ok}/{n}. Yangi urinish — keyingi haftadan.",
    },
    # --- экзамен дня ---
    "exam_intro": {
        "ru": "🎓 <b>Экзамен дня</b>: {n} вопросов, нужно не менее {need}% верных.\n"
              "Попытка одна в сутки. За сдачу — +{xp} XP. Удачи!",
        "uz": "🎓 <b>Kun imtihoni</b>: {n} ta savol, kamida {need}% to'g'ri javob kerak.\n"
              "Kuniga bitta urinish. Topshirsangiz — +{xp} XP. Omad!",
    },
    "exam_used": {
        "ru": "Сегодняшний экзамен уже начат. Следующий — завтра.",
        "uz": "Bugungi imtihon allaqachon boshlangan. Keyingisi — ertaga.",
    },
    "exam_few": {
        "ru": "Для экзамена нужно хотя бы {min} слов. Получи слова дня: /today",
        "uz": "Imtihon uchun kamida {min} ta so'z kerak. Kun so'zlari: /today",
    },
    "exam_passed": {
        "ru": "🎓 Экзамен сдан: {ok}/{n}! +{xp} XP",
        "uz": "🎓 Imtihon topshirildi: {ok}/{n}! +{xp} XP",
    },
    "exam_failed": {
        "ru": "❌ Экзамен не сдан: {ok}/{n}. Повтори слова (/review) и приходи завтра.",
        "uz": "❌ Imtihon topshirilmadi: {ok}/{n}. So'zlarni takrorlang (/review), ertaga qayting.",
    },
    "bonus_text": {
        "ru": "💰 <b>Бонусы</b>\n\nУсловия на этой неделе:\n"
              "{ok_days} Активных дней: {days}/{need_days}\n"
              "{ok_acc} Точность ответов: {acc}% (нужно {need_acc}%+)\n"
              "{ok_test} Недельный тест: {test}\n\n"
              "Бонус даётся за топ недели, 30 дней серии и 100 выученных слов. "
              "Выплата — после проверки администратором.\n\n{history}",
        "uz": "💰 <b>Bonuslar</b>\n\nShu haftadagi shartlar:\n"
              "{ok_days} Faol kunlar: {days}/{need_days}\n"
              "{ok_acc} Javoblar aniqligi: {acc}% (kerak {need_acc}%+)\n"
              "{ok_test} Haftalik test: {test}\n\n"
              "Bonus hafta topi, 30 kunlik seriya va 100 ta o'zlashtirilgan so'z uchun "
              "beriladi. To'lov — administrator tekshiruvidan so'ng.\n\n{history}",
    },
    "bonus_test_passed": {"ru": "сдан", "uz": "topshirildi"},
    "bonus_test_failed": {"ru": "не сдан", "uz": "topshirilmadi"},
    "bonus_test_todo": {"ru": "не пройден (/weektest)", "uz": "topshirilmagan (/weektest)"},
    "bonus_history_title": {"ru": "<b>Твои бонусы:</b>", "uz": "<b>Sizning bonuslaringiz:</b>"},
    "bonus_history_empty": {
        "ru": "Пока бонусов нет — всё впереди!",
        "uz": "Hozircha bonus yo'q — hammasi oldinda!",
    },
    "bonus_reason_top_week": {"ru": "топ недели", "uz": "hafta topi"},
    "bonus_reason_streak_30": {"ru": "30 дней подряд", "uz": "ketma-ket 30 kun"},
    "bonus_reason_words_100": {"ru": "100 выученных слов", "uz": "100 ta o'zlashtirilgan so'z"},
    "bonus_status_pending": {"ru": "на проверке", "uz": "tekshiruvda"},
    "bonus_status_paid": {"ru": "выплачен", "uz": "to'langan"},
    "bonus_status_rejected": {"ru": "отклонён", "uz": "rad etilgan"},
    "bonus_paid_notice": {
        "ru": "🎁 Тебе выплачен бонус: {amount} ({reason}). Так держать!",
        "uz": "🎁 Sizga bonus to'landi: {amount} ({reason}). Shunday davom eting!",
    },
    # --- награды ---
    "reward_xp": {"ru": "⭐ +{xp} XP", "uz": "⭐ +{xp} XP"},
    "reward_xp_capped": {
        "ru": "Дневной лимит XP достигнут — завтра снова зарабатывай!",
        "uz": "Kunlik XP limiti to'ldi — ertaga yana to'plang!",
    },
    "reward_streak": {"ru": "🔥 Серия: {n} дн.", "uz": "🔥 Seriya: {n} kun"},
    "reward_freeze_used": {
        "ru": "🧊 Заморозка сохранила серию (использовано: {n})",
        "uz": "🧊 Muzlatish seriyani saqlab qoldi (ishlatildi: {n})",
    },
    "reward_freeze_earned": {
        "ru": "🧊 Ты получил заморозку серии!",
        "uz": "🧊 Siz seriya muzlatgichini oldingiz!",
    },
    "reward_level_up": {"ru": "🎉 Новый уровень: {level}!", "uz": "🎉 Yangi daraja: {level}!"},
    "badge_new": {"ru": "🏅 Новое достижение: {name}", "uz": "🏅 Yangi yutuq: {name}"},
    "badge_first_quiz": {"ru": "🌱 Первая викторина", "uz": "🌱 Birinchi viktorina"},
    "badge_streak_7": {"ru": "🔥 7 дней подряд", "uz": "🔥 Ketma-ket 7 kun"},
    "badge_streak_30": {"ru": "🏆 30 дней подряд", "uz": "🏆 Ketma-ket 30 kun"},
    "badge_words_10": {"ru": "📘 10 выученных слов", "uz": "📘 10 ta o'zlashtirilgan so'z"},
    "badge_words_100": {"ru": "📚 100 выученных слов", "uz": "📚 100 ta o'zlashtirilgan so'z"},
    "badge_perfect_quiz": {"ru": "💯 Викторина без ошибок", "uz": "💯 Xatosiz viktorina"},
    "badge_xp_1000": {"ru": "⭐ 1000 XP", "uz": "⭐ 1000 XP"},
    # --- статистика ---
    "stats_text": {
        "ru": "📊 <b>Твоя статистика</b>\n\n"
              "Уровень {level}: {bar}\nОсвоено слов уровня: {mastered}/{total}\n"
              "⭐ XP: {xp}\n🔥 Серия: {streak} дн. · 🧊 заморозок: {freezes}\n\n"
              "📚 Получено слов: {given}, выучено: {learned}\n\n"
              "<b>Эта неделя</b>\nОтветов: {answers} · верно: {accuracy}%\n"
              "Активных дней: {days}/7 · XP: {week_xp}\n\n"
              "🏅 Достижения: {badges}",
        "uz": "📊 <b>Sizning statistikangiz</b>\n\n"
              "Daraja {level}: {bar}\nDarajadagi o'zlashtirilgan so'zlar: {mastered}/{total}\n"
              "⭐ XP: {xp}\n🔥 Seriya: {streak} kun · 🧊 muzlatgichlar: {freezes}\n\n"
              "📚 Olingan so'zlar: {given}, o'zlashtirilgan: {learned}\n\n"
              "<b>Shu hafta</b>\nJavoblar: {answers} · to'g'ri: {accuracy}%\n"
              "Faol kunlar: {days}/7 · XP: {week_xp}\n\n"
              "🏅 Yutuqlar: {badges}",
    },
    "stats_no_badges": {"ru": "пока нет", "uz": "hozircha yo'q"},
    "streak_text": {
        "ru": "🔥 Серия: <b>{streak}</b> дн.\n🧊 Заморозок: {freezes} "
              "(новая — за каждые 7 дней серии)\n"
              "Активный день — минимум {need} ответа в викторине.\n\n{status}",
        "uz": "🔥 Seriya: <b>{streak}</b> kun\n🧊 Muzlatgichlar: {freezes} "
              "(yangisi — har 7 kunlik seriya uchun)\n"
              "Faol kun — viktorinada kamida {need} ta javob.\n\n{status}",
    },
    "streak_done": {"ru": "✅ Сегодня уже засчитано!", "uz": "✅ Bugun hisoblandi!"},
    "streak_risk": {
        "ru": "⚠️ Пройди /quiz сегодня, чтобы сохранить серию.",
        "uz": "⚠️ Seriyani saqlash uchun bugun /quiz ni bajaring.",
    },
    "streak_none": {
        "ru": "Пройди /quiz, чтобы начать новую серию.",
        "uz": "Yangi seriyani boshlash uchun /quiz ni bajaring.",
    },
    "weekly_report": {
        "ru": "📅 <b>Итоги недели</b>\n\nОтветов: {answers}, верно: {accuracy}%\n"
              "Активных дней: {days}/7\n⭐ XP за неделю: {xp}\n📚 Новых слов: {given}\n"
              "🔥 Серия: {streak} дн.\n\nТак держать!",
        "uz": "📅 <b>Hafta yakunlari</b>\n\nJavoblar: {answers}, to'g'ri: {accuracy}%\n"
              "Faol kunlar: {days}/7\n⭐ Hafta XP: {xp}\n📚 Yangi so'zlar: {given}\n"
              "🔥 Seriya: {streak} kun\n\nShunday davom eting!",
    },
    # --- повторение ---
    "review_title": {
        "ru": "🔁 Повторение · осталось: {left}",
        "uz": "🔁 Takrorlash · qoldi: {left}",
    },
    "review_prompt": {
        "ru": "Вспомни перевод, затем нажми кнопку.",
        "uz": "Tarjimasini eslang, so'ng tugmani bosing.",
    },
    "review_show_btn": {"ru": "👀 Показать ответ", "uz": "👀 Javobni ko'rsatish"},
    "review_ok_btn": {"ru": "✅ Помню", "uz": "✅ Eslayman"},
    "review_no_btn": {"ru": "❌ Не помню", "uz": "❌ Eslolmayman"},
    "review_done": {
        "ru": "✅ На сегодня всё повторено!",
        "uz": "✅ Bugungi takrorlash tugadi!",
    },
    "review_next": {
        "ru": "Ближайшее повторение: {when}",
        "uz": "Keyingi takrorlash: {when}",
    },
    "review_no_words": {
        "ru": "Новые слова — в /today",
        "uz": "Yangi so'zlar — /today da",
    },
    "welcome_back": {
        "ru": "С возвращением! Загляни в /today за словами дня.",
        "uz": "Qaytganingiz bilan! Kun so'zlari uchun /today ni bosing.",
    },
    "help": {
        "ru": "<b>WordDay</b> — новые английские слова каждый день (по {n} в день).\n\n"
              "/today — слова дня\n/quiz — викторина\n/exam — экзамен дня\n/review — повторение\n"
              "/stats — статистика\n/streak — серия дней\n/theme — сменить тему\n"
              "/settings — настройки\n/help — эта справка",
        "uz": "<b>WordDay</b> — har kuni yangi inglizcha so'zlar (kuniga {n} tadan).\n\n"
              "/today — kun so'zlari\n/quiz — viktorina\n/exam — kun imtihoni\n/review — takrorlash\n"
              "/stats — statistika\n/streak — kunlar seriyasi\n/theme — mavzuni almashtirish\n"
              "/settings — sozlamalar\n/help — shu yordam",
    },
}


def t(lang: Language | str, key: str, **kwargs: object) -> str:
    """Текст по ключу на нужном языке; неизвестный язык -> русский."""
    code = lang.value if isinstance(lang, Language) else lang
    variants = TEXTS[key]
    text = variants.get(code) or variants["ru"]
    return text.format(**kwargs) if kwargs else text


def fmt_sum(amount: int) -> str:
    """5000 -> '5 000 сум' (разряды разделены неразрывным пробелом)."""
    return f"{amount:,}".replace(",", chr(0xA0)) + " сум"
