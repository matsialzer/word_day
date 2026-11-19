"""Страховка от «забытого» роутера: каждый модуль с обработчиками обязан быть подключён."""
import importlib
import pkgutil

from aiogram import Router

import worddays.bot.handlers as handlers_pkg
from worddays.bot.handlers import all_routers


def test_every_handler_module_is_registered():
    registered = {id(r) for r in all_routers()}
    missing = []
    for info in pkgutil.iter_modules(handlers_pkg.__path__):
        module = importlib.import_module(f"worddays.bot.handlers.{info.name}")
        router = getattr(module, "router", None)
        if isinstance(router, Router) and id(router) not in registered:
            missing.append(info.name)
    assert not missing, f"не подключены в all_routers(): {missing}"


def test_routers_are_unique_and_error_handler_first():
    routers = all_routers()
    assert len({id(r) for r in routers}) == len(routers)
    assert routers[0].name == "common"
