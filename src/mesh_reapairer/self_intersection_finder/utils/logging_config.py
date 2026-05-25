"""
Настройка логирования для модуля поиска самопересечений.

Формат логов: [YYYY-MM-DD HH:MM:SS] [MODULE.function] LEVEL: MESSAGE

Поддерживает переменные окружения:
- MESH_REAPAIRER_LOG_LEVEL: уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- MESH_REAPAIRER_LOG_FILE: путь к файлу логов
- MESH_REAPAIRER_LOG_STDOUT: 0/1 для отключения/включения вывода в консоль
"""
import logging
import os
import sys
from typing import Optional


def setup_logger(
    name: str = 'self_intersection_finder',
    level: str = 'INFO',
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Настроить логгер для модуля.

    Приоритет настроек:
    1. Переменные окружения (MESH_REAPAIRER_LOG_LEVEL, MESH_REAPAIRER_LOG_FILE, MESH_REAPAIRER_LOG_STDOUT)
    2. Root logger (если уже настроен)
    3. Параметры функции

    Args:
        name: Имя логгера
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Опциональный путь к файлу логов (если None, только консоль)

    Returns:
        Настроенный логгер

    Example:
        >>> logger = setup_logger('bvh_builder', 'DEBUG')
        >>> logger.info("Building BVH tree")
        [2026-04-09 10:30:45] [bvh_builder.build] INFO: Building BVH tree
    """
    logger = logging.getLogger(name)

    # Переменные окружения имеют наивысший приоритет
    env_level = os.getenv('MESH_REAPAIRER_LOG_LEVEL', level).upper()
    env_log_file = os.getenv('MESH_REAPAIRER_LOG_FILE', log_file)
    env_log_stdout = os.getenv('MESH_REAPAIRER_LOG_STDOUT', '1') == '1'

    # Преобразуем строку уровня в константу
    numeric_level = getattr(logging, env_level, logging.INFO)
    logger.setLevel(numeric_level)

    # Если root logger уже настроен (есть handlers), используем его
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Пропагируем логи к root logger
        logger.propagate = True
        return logger

    # Если у логгера уже есть обработчики, не добавляем новые
    if logger.handlers:
        return logger

    # Формат логов
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s.%(funcName)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (stdout) - только если включен
    if env_log_stdout:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler (optional)
    if env_log_file:
        file_handler = logging.FileHandler(env_log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Не пропагировать логи в root logger (избежать дубликатов)
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получить существующий логгер по имени.

    Args:
        name: Имя логгера

    Returns:
        Логгер (может быть не настроен, если setup_logger не вызывался)
    """
    return logging.getLogger(name)


# Готовые имена логгеров для компонентов
LOGGER_NAMES = {
    'main': 'self_intersection_finder',
    'bvh_builder': 'self_intersection_finder.bvh.builder',
    'bvh_traverser': 'self_intersection_finder.bvh.traverser',
    'classifier': 'self_intersection_finder.intersection.classifier',
    'segment_finder': 'self_intersection_finder.intersection.segment_finder',
    'parallel_handler': 'self_intersection_finder.intersection.parallel_handler',
    'pair_cache': 'self_intersection_finder.caching.pair_cache',
}
