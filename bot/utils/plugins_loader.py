"""Автозагрузка плагинов цепей (Solana, Base и т.д.)."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

from loguru import logger


def load_chain_plugins(
    package_path: str = "plugins",
    context: dict | None = None,
) -> list[ModuleType]:
    """Ищет модули в каталоге plugins и импортирует их."""

    base_path = Path(package_path)
    if not base_path.exists():
        logger.debug("Каталог плагинов {path} отсутствует", path=base_path)
        return []

    package_name = base_path.name
    loaded: list[ModuleType] = []

    for module_info in pkgutil.iter_modules([str(base_path)]):
        full_name = f"{package_name}.{module_info.name}"
        try:
            module = importlib.import_module(full_name)
        except Exception as exc:  # noqa: BLE001
            logger.error("Плагин {module} не загрузился: {error}", module=full_name, error=exc)
            continue
        loaded.append(module)
        if context and hasattr(module, "init_plugin"):
            try:
                module.init_plugin(context)
            except Exception as exc:  # noqa: BLE001
                logger.error("init_plugin {module} упал: {error}", module=full_name, error=exc)
                continue
        logger.info("Плагин {module} подключён", module=full_name)
    return loaded


__all__ = ["load_chain_plugins"]

