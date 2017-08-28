#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import OrderedDict
from typing import Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict  # noqa: F401


class Multimap(object):
    def __init__(self) -> None:
        # maybe defaultdict(set) is better
        self._map: OrderedDict[str, List[Any]] = OrderedDict()

    def set(self, key: str, value: Any) -> None:
        _set = self._map.get(key)
        if not _set:
            _set = list()
            self._map[key] = _set
        if value not in _set:
            _set.append(value)

    def get(self, key: str) -> List[Any]:
        return self._map.get(key, list())

    def has(self, key: str) -> bool:
        return key in self._map

    def hasValue(self, key: str, value: Any) -> bool:
        _set = self._map.get(key, list())
        return value in _set

    def size(self) -> int:
        return len(self._map)

    def delete(self, key: str, value: Any) -> bool:
        values = self.get(key)
        result = value in values
        if result:
            values.remove(value)
        if len(values) == 0:
            self._map.pop(key)
        return result

    def deleteAll(self, key: str) -> None:
        self._map.pop(key, None)

    def firstValue(self, key: str) -> Any:
        _set = self._map.get(key)
        if not _set:
            return None
        return _set[0]

    def firstKey(self) -> str:
        return next(iter(self._map.keys()))

    def valuesArray(self) -> List[Any]:
        result: List[Any] = list()
        for values in self._map.values():
            result.extend(values)
        return result

    def clear(self) -> None:
        self._map.clear()
