"""
反撤回插件 (Anti-Recall)
监听群聊中的撤回事件，艾特撤回者并将被撤回的消息重新发送出来。
"""

import time
from collections import defaultdict

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp


@register(
    "astrbot_plugin_anti_recall",
    "Happy",
    "反撤回插件：群里有人撤回消息时，艾特那个人并发出被撤回的消息",
    "1.0.0",
)
class AntiRecall(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 消息缓存：group_id -> {message_id: {content, sender_id, sender_name, timestamp}}
        self._cache: dict[str, dict] = defaultdict(dict)
        self._cache_ttl: int = 600  # 缓存过期时间（秒），默认 10 分钟

    async def initialize(self):
        """插件初始化时调用"""
        logger.info("[反撤回] 插件已加载，开始守护群聊消息~")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_event(self, event: AstrMessageEvent):
        """监听所有群聊消息事件，缓存消息并在检测到撤回时发出提醒"""
        abm = event.message_obj
        raw = abm.raw_message

        # 尝试以 dict 方式读取原始事件（兼容 aiocqhttp / OneBot v11）
        try:
            get = raw.get if hasattr(raw, "get") else None
        except Exception:
            return
        if get is None:
            return

        post_type = get("post_type", "")

        if post_type == "message":
            # ---------- 普通消息：缓存 ----------
            group_id = str(get("group_id", ""))
            message_id = str(get("message_id", ""))
            sender = get("sender", {})
            sender_id = str(sender.get("user_id", "")) if isinstance(sender, dict) else ""
            sender_name = ""
            if isinstance(sender, dict):
                sender_name = sender.get("card") or sender.get("nickname", "未知")

            if group_id and message_id:
                self._cache[group_id][message_id] = {
                    "content": abm.message_str or "[非文本消息]",
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "timestamp": time.time(),
                }

        elif post_type == "notice":
            # ---------- 通知事件：检查是否为撤回 ----------
            notice_type = get("notice_type", "")
            if notice_type != "group_recall":
                return

            group_id = str(get("group_id", ""))
            message_id = str(get("message_id", ""))
            # user_id: 被撤回消息的原发送者
            # operator_id: 执行撤回操作的人（可能是本人或管理员）
            operator_id = str(get("operator_id", ""))
            user_id = str(get("user_id", ""))

            # 优先艾特执行撤回的人
            at_target = operator_id or user_id

            # 查找缓存
            cached = self._cache.get(group_id, {}).pop(message_id, None)

            # 定期清理过期缓存
            self._clean_expired(group_id)

            if cached:
                original_sender = cached["sender_name"] or "未知"
                original_content = cached["content"] or "[空消息]"

                # 如果撤回者和原发送者不同，补充说明
                if operator_id and user_id and operator_id != user_id:
                    chain = [
                        Comp.At(qq=at_target),
                        Comp.Plain(
                            f" 撤回了 {original_sender} 的一条消息：\n{original_content}"
                        ),
                    ]
                else:
                    chain = [
                        Comp.At(qq=at_target),
                        Comp.Plain(f" 撤回了自己的一条消息：\n{original_content}"),
                    ]
                yield event.chain_result(chain)
            else:
                # 缓存未命中
                chain = [
                    Comp.At(qq=at_target) if at_target else Comp.Plain(""),
                    Comp.Plain(" 刚刚撤回了条消息，但我没来得及记录 😢"),
                ]
                yield event.chain_result(chain)

    def _clean_expired(self, group_id: str) -> None:
        """清理指定群聊中过期的消息缓存"""
        now = time.time()
        cache = self._cache.get(group_id, {})
        expired = [
            mid
            for mid, data in cache.items()
            if now - data.get("timestamp", 0) > self._cache_ttl
        ]
        for mid in expired:
            del cache[mid]

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("[反撤回] 插件已卸载")
        self._cache.clear()

