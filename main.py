from __future__ import annotations

from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Image
from astrbot.api.star import Context, Star, register

from .deck_loader import discover_decks, find_match, resolve_deck_order


@register(
    "astrbot_plugin_playcards",
    "Omnisch",
    "关键词触发打出《杀戮尖塔》系列等游戏卡牌",
    "2.0.0",
    "https://github.com/Omnisch/astrbot_plugin_playcards",
)
class PlaycardsPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        self.plugin_dir = Path(__file__).resolve().parent
        self.decks = discover_decks(self.plugin_dir / "decks", logger=logger)
        self.deck_order = resolve_deck_order(
            self.decks,
            self.config.get("enabled_decks", ["sts", "sts2"]),
            self.config.get("deck_priority", ["sts2", "sts"]),
        )
        loaded = ", ".join(
            f"{deck.deck_id}({len(deck.card_dict)})" for deck in self.deck_order
        )
        logger.info(
            f"[Playcards] 已发现 {len(self.decks)} 个卡组；启用顺序: {loaded or '无'}"
        )

    def _pick_match(self, message: str):
        return find_match(
            message,
            self.deck_order,
            case_sensitive=self.config.get("case_sensitive", True),
        )

    def _is_session_allowed(self, event: AstrMessageEvent) -> bool:
        whitelist = self.config.get("session_whitelist", [])
        if not isinstance(whitelist, list):
            return False
        session_id = getattr(event.message_obj, "session_id", "")  # 文档字段：session_id
        return session_id in whitelist

    def _is_command_like(self, text: str) -> bool:
        s = (text or "").lstrip()
        return s.startswith(("/", "!", "@", "#"))  # 可以在此添加其他前缀

    def _is_at_me(self, event) -> bool:
        self_id = getattr(event.message_obj, "self_id", None)
        if not self_id:
            return False
        for comp in getattr(event.message_obj, "message", []) or []:
            if isinstance(comp, At):
                # 不同适配器 At 字段可能叫 qq / user_id 等，按平台调整
                target = getattr(comp, "qq", None) or getattr(comp, "user_id", None)
                if str(target) == str(self_id):
                    return True
        return False

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_any_message(self, event: AstrMessageEvent):
        # 1) 仅监听白名单会话
        if not self._is_session_allowed(event):
            return

        # 2) 只看纯文本
        text = event.message_str or ""
        if not text:
            return

        # 3.1) 排除形如命令的消息
        if self._is_command_like(text):
            return
        # 3.2) 排除 @ 机器人的消息
        if self._is_at_me(event):
            return

        match = self._pick_match(text)
        if match is None:
            return

        logger.info(
            f"[Playcards] 命中 deck={match.deck_id!r}, key={match.keyword!r} "
            f"-> id={match.card_id!r} -> {match.image_path.name}"
        )

        yield event.chain_result([Image.fromFileSystem(str(match.image_path))])
        return
