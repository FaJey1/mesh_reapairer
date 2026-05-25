"""
Кэш проверенных пар граней.

Оптимизирован для быстрого доступа: O(1) проверка, без sorted().
"""
from typing import Set, Tuple, Dict


class PairCache:
    """
    Кэш проверенных пар граней.

    Реализует интерфейс IPairCache из domain.interfaces.

    Оптимизации:
    - Использует set для O(1) проверки
    - Нормализация пар (id1, id2) через if/swap вместо sorted()
    - Отслеживает статистику попаданий/промахов
    """

    def __init__(self):
        """Инициализация пустого кэша."""
        self._cache: Set[Tuple[int, int]] = set()
        self._hits: int = 0
        self._misses: int = 0

    def is_checked(self, id1: int, id2: int) -> bool:
        """
        Проверить, была ли пара уже проверена.

        Args:
            id1, id2: ID граней

        Returns:
            True если пара уже проверена
        """
        # ОПТИМИЗАЦИЯ: нормализуем пару без sorted()
        if id1 > id2:
            id1, id2 = id2, id1

        if (id1, id2) in self._cache:
            self._hits += 1
            return True

        self._misses += 1
        return False

    def mark_checked(self, id1: int, id2: int) -> None:
        """
        Пометить пару как проверенную.

        Args:
            id1, id2: ID граней
        """
        # Нормализуем пару
        if id1 > id2:
            id1, id2 = id2, id1

        self._cache.add((id1, id2))

    def stats(self) -> Dict[str, any]:
        """
        Получить статистику кэша.

        Returns:
            Словарь с метриками:
            - size: количество пар в кэше
            - hits: количество попаданий
            - misses: количество промахов
            - hit_rate: процент попаданий
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            'size': len(self._cache),
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': hit_rate
        }

    def clear(self) -> None:
        """Очистить кэш и статистику."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def __len__(self) -> int:
        """Количество пар в кэше."""
        return len(self._cache)

    def __contains__(self, pair: Tuple[int, int]) -> bool:
        """Проверить наличие пары в кэше."""
        id1, id2 = pair
        if id1 > id2:
            id1, id2 = id2, id1
        return (id1, id2) in self._cache
