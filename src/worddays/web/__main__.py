"""Запуск веб-панели: python -m worddays.web"""
import logging

import uvicorn

from worddays.config import get_settings
from worddays.logging_conf import setup_logging
from worddays.web.app import create_app


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    app = create_app(settings)
    logging.getLogger(__name__).info("Веб-панель: http://%s:%d", settings.web_host,
                                     settings.web_port)
    uvicorn.run(app, host=settings.web_host, port=settings.web_port, log_level="warning")


if __name__ == "__main__":
    main()
