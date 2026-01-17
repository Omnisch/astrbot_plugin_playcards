from __future__ import annotations

import random
from pathlib import Path
from typing import List, Optional, Tuple

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Image
from astrbot.api.star import Context, Star, register

# 尝试导入 rev_dict
try:
    from .rev_dict import rev_dict  # type: ignore
except Exception as e:
    rev_dict = {}
    logger.exception(f"[Playcards] Failed to import rev_dict from rev_dict.py: {e}")


@register(
    "astrbot_plugin_playcards",
    "Omnisch",
    "关键词触发打出三国杀、杀戮尖塔等卡牌",
    "1.2.0",
    "https://github.com/Omnisch/astrbot_plugin_playcards",
)
class PlaycardsPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 插件目录与卡牌目录
        self.plugin_dir = Path(__file__).resolve().parent
        self.card_dir = self.plugin_dir / "cards"

        # 预处理 keys (按长度降序能让“更具体/更长的 key”优先命中)
        self._keys_sorted: List[str] = sorted((rev_dict or {}).keys(), key=len, reverse=True)

        logger.info(
            f"[Playcards] loaded: keys={len(self._keys_sorted)}, card_dir={self.card_dir}"
        )

    def _normalize(self, s: str) -> str:
        return s if self.config.get("case_sensitive", True) else s.lower()

    def _pick_match(self, message: str) -> Optional[Tuple[str, str]]:
        """
        返回 (matched_key, picked_id) 或 None
        """
        if not self._keys_sorted:
            return None

        msg = self._normalize(message)

        for k in self._keys_sorted:
            kk = self._normalize(k)
            if kk and kk in msg:
                ids: List[str] = list(rev_dict.get(k, []))  # 原始 key 取值
                if not ids:
                    continue
                picked = random.choice(ids)
                return (k, picked)

        return None

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
        # 1) 总开关
        if not self.config.get("enabled", True):
            return

        # 2) 仅监听白名单会话
        if not self._is_session_allowed(event):
            return

        # 3) 只看纯文本
        text = event.message_str or ""
        if not text:
            return
        
        # 排除命令样消息
        if self._is_command_like(text):
            return
        # 排除 @ 机器人的消息
        if self._is_at_me(event):
            return

        match = self._pick_match(text)
        if not match:
            return

        matched_key, picked_id = match
        img_path = self.card_dir / f"{picked_id}.png"

        if not img_path.exists():
            logger.warning(
                f"[Playcards] image not found: {img_path} (matched_key={matched_key})"
            )
            return

        logger.info(
            f"[Playcards] hit key={matched_key!r} -> id={picked_id!r} -> {img_path.name}"
        )

        # 4) 发送图片：本地文件
        yield event.chain_result([Image.fromFileSystem(str(img_path))])

        # 5) 命中后是否只触发一次（本实现默认本来就只发一次）
        # first_match_only 用于未来“同一条消息多 key 多次触发”的扩展，这里保留配置字段。
        return
