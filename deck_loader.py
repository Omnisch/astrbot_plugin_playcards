from __future__ import annotations

import importlib.util
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".webp", ".gif", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class Deck:
    deck_id: str
    name: str
    root: Path
    card_dir: Path
    card_dict: Mapping[str, Sequence[str]]
    reverse_dict: Mapping[str, Sequence[str]]
    keys_sorted: Sequence[str]
    images_by_id: Mapping[str, Path]


@dataclass(frozen=True)
class CardMatch:
    deck_id: str
    deck_name: str
    keyword: str
    card_id: str
    image_path: Path


def _load_python_card_dict(path: Path, deck_id: str) -> dict[str, list[str]]:
    module_name = f"playcards_deck_{deck_id}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载卡牌字典: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value = getattr(module, "card_dict", None)
    if not isinstance(value, dict):
        raise TypeError(f"{path} 必须导出 dict 类型的 card_dict")

    result: dict[str, list[str]] = {}
    for card_id, aliases in value.items():
        if not isinstance(card_id, str) or not card_id:
            raise ValueError(f"{path} 包含无效卡牌 ID: {card_id!r}")
        if not isinstance(aliases, (list, tuple)):
            raise TypeError(f"{path} 中 {card_id!r} 的关键字必须是列表")
        cleaned = []
        for alias in aliases:
            if not isinstance(alias, str) or not alias:
                raise ValueError(f"{path} 中 {card_id!r} 包含无效关键字")
            if alias not in cleaned:
                cleaned.append(alias)
        if not cleaned:
            raise ValueError(f"{path} 中 {card_id!r} 没有可用关键字")
        result[card_id] = cleaned
    return result


def _index_images(card_dir: Path) -> dict[str, Path]:
    images: dict[str, Path] = {}
    for path in sorted(card_dir.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in SUPPORTED_IMAGE_EXTENSIONS:
            continue
        card_id = path.stem
        if card_id in images:
            raise ValueError(
                f"卡组中存在重复文件名（忽略路径和扩展名后）: "
                f"{images[card_id]} / {path}"
            )
        images[card_id] = path
    return images


def _build_reverse_dict(
    card_dict: Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = {}
    for card_id, aliases in card_dict.items():
        for alias in aliases:
            ids = reverse.setdefault(alias, [])
            if card_id not in ids:
                ids.append(card_id)
    return reverse


def load_deck(deck_root: Path) -> Deck:
    manifest_path = deck_root / "deck.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    deck_id = manifest.get("id")
    name = manifest.get("name")
    if not isinstance(deck_id, str) or not deck_id:
        raise ValueError(f"{manifest_path} 缺少有效的 id")
    if deck_id != deck_root.name:
        raise ValueError(f"卡组 id {deck_id!r} 必须与目录名 {deck_root.name!r} 一致")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{manifest_path} 缺少有效的 name")

    dictionary_path = deck_root / manifest.get("dictionary", "card_dict.py")
    card_dir = deck_root / manifest.get("cards", "cards")
    if not dictionary_path.is_file():
        raise FileNotFoundError(dictionary_path)
    if not card_dir.is_dir():
        raise FileNotFoundError(card_dir)

    card_dict = _load_python_card_dict(dictionary_path, deck_id)
    images = _index_images(card_dir)
    missing_images = sorted(set(card_dict) - set(images))
    if missing_images:
        preview = ", ".join(missing_images[:10])
        raise ValueError(f"卡组 {deck_id!r} 有 {len(missing_images)} 张卡缺图: {preview}")

    reverse = _build_reverse_dict(card_dict)
    keys_sorted = tuple(sorted(reverse, key=lambda key: (-len(key), key.casefold(), key)))
    return Deck(
        deck_id=deck_id,
        name=name,
        root=deck_root,
        card_dir=card_dir,
        card_dict=card_dict,
        reverse_dict=reverse,
        keys_sorted=keys_sorted,
        images_by_id=images,
    )


def discover_decks(decks_root: Path, logger=None) -> dict[str, Deck]:
    decks: dict[str, Deck] = {}
    if not decks_root.is_dir():
        return decks
    for deck_root in sorted(path for path in decks_root.iterdir() if path.is_dir()):
        if not (deck_root / "deck.json").is_file():
            continue
        try:
            deck = load_deck(deck_root)
        except Exception:
            if logger is None:
                raise
            logger.exception(f"[Playcards] 加载卡组失败: {deck_root}")
            continue
        if deck.deck_id in decks:
            raise ValueError(f"重复卡组 id: {deck.deck_id}")
        decks[deck.deck_id] = deck
    return decks


def _string_list(value, default: Sequence[str]) -> list[str]:
    if not isinstance(value, (list, tuple)):
        value = default
    result = []
    for item in value:
        if isinstance(item, str) and item and item not in result:
            result.append(item)
    return result


def resolve_deck_order(
    decks: Mapping[str, Deck],
    enabled_decks,
    deck_priority,
) -> list[Deck]:
    enabled_ids = _string_list(enabled_decks, tuple(decks))
    if "*" in enabled_ids:
        enabled_ids = list(decks)
    enabled = {deck_id for deck_id in enabled_ids if deck_id in decks}

    priority_ids = _string_list(deck_priority, ())
    ordered_ids = [deck_id for deck_id in priority_ids if deck_id in enabled]
    ordered_ids.extend(sorted(enabled - set(ordered_ids)))
    return [decks[deck_id] for deck_id in ordered_ids]


def find_match(
    message: str,
    ordered_decks: Iterable[Deck],
    case_sensitive: bool = True,
    chooser: Callable[[Sequence[str]], str] = random.choice,
) -> Optional[CardMatch]:
    normalized_message = message if case_sensitive else message.casefold()
    for deck in ordered_decks:
        for keyword in deck.keys_sorted:
            normalized_keyword = keyword if case_sensitive else keyword.casefold()
            if normalized_keyword and normalized_keyword in normalized_message:
                card_id = chooser(deck.reverse_dict[keyword])
                return CardMatch(
                    deck_id=deck.deck_id,
                    deck_name=deck.name,
                    keyword=keyword,
                    card_id=card_id,
                    image_path=deck.images_by_id[card_id],
                )
    return None
