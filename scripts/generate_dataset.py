"""Удобный скрипт-обертка для быстрого запуска генератора.

Полный CSV-файл я храню в Google Drive и НИКОГДА не загружаю в Git-репозиторий.
"""

from leo_data_pipeline.cli import main

if __name__ == "__main__":
    # Запускаю команду "generate" через CLI (интерфейс командной строки) пакета.
    main(["generate"])
