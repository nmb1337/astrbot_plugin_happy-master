"""
反撤回插件 (Anti-Recall)
监听群聊中的撤回事件，艾特撤回者并将被撤回的消息重新发送出来。

支持的平台：aiocqhttp (OneBot v11, 如 NapCat / Lagrange)
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
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        # 消息缓存：group_id -> {message_id: {content, sender_id, sender_name, timestamp}}
        self._cache: dict[str, dict] = defaultdict(dict)
        self._cache_ttl: int = 600  # 缓存过期时间（秒），默认 10 分钟
        # 白名单配置
        self._whitelist: list[str] = []
        # 群白名单：只有列表内的群才启用反撤回，空列表表示全部群启用
        self._group_whitelist: list[str] = []
        if config and isinstance(config, dict):
            self._whitelist = [str(u) for u in config.get("whitelist", [])]
            self._group_whitelist = [str(g) for g in config.get("group_whitelist", [])]
        # 群成员角色缓存：group_id -> {user_id: role}，避免频繁调 API
        self._role_cache: dict[str, dict[str, str]] = defaultdict(dict)

    async def initialize(self):
        """插件初始化时调用"""
        logger.info("[反撤回] 插件已加载，开始守护群聊消息~")

    # 同时使用 ALL 消息类型 + AIOCQHTTP 平台过滤，确保不漏事件
    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def on_group_event(self, event: AstrMessageEvent):
        """监听所有群聊消息事件，缓存消息并在检测到撤回时发出提醒"""
        abm = event.message_obj
        raw = abm.raw_message

        # ---------- 解析 raw_message ----------
        # aiocqhttp 的 raw_message 是 dict-like 的 Event 对象
        if raw is None:
            return
        try:
            post_type = raw.get("post_type", "")
            group_id = str(raw.get("group_id", ""))
        except Exception as e:
            logger.info(
                f"[反撤回] 无法读取 raw_message (type={type(raw).__name__})，"
                f"可能不是 OneBot 事件，跳过。err={e}"
            )
            return

        # 群白名单检查：配置了白名单时，只处理白名单内的群
        if self._group_whitelist and group_id:
            if group_id not in self._group_whitelist:
                return

        if post_type == "message":
            # ---------- 普通消息：缓存 ----------
            if not group_id:
                return  # 非群聊消息，跳过

            message_id = str(raw.get("message_id", ""))
            if not message_id:
                return

            sender = raw.get("sender", {})
            if isinstance(sender, dict):
                sender_name = sender.get("card") or sender.get("nickname", "未知")
                sender_id = str(sender.get("user_id", ""))
            else:
                sender_name = "未知"
                sender_id = ""

            self._cache[group_id][message_id] = {
                "content": abm.message_str or "[非文本消息]",
                "sender_id": sender_id,
                "sender_name": sender_name,
                "timestamp": time.time(),
            }
            # 顺便缓存发送者角色（OneBot 消息事件 sender 中自带 role）
            sender_role = sender.get("role", "") if isinstance(sender, dict) else ""
            if sender_id and sender_role:
                self._role_cache[group_id][sender_id] = sender_role

        elif post_type == "notice":
            # ---------- 通知事件：检查是否为撤回 ----------
            notice_type = raw.get("notice_type", "")

            logger.info(
                f"[反撤回] 收到通知事件 notice_type={notice_type}"
            )

            if notice_type != "group_recall":
                return

            # 撤回事件关键字段
            message_id = str(raw.get("message_id", ""))  # 被撤回的消息 ID
            user_id = str(raw.get("user_id", ""))  # 被撤回消息的原发送者
            operator_id = str(raw.get("operator_id", ""))  # 执行撤回操作的人

            logger.info(
                f"[反撤回] 检测到撤回事件 group={group_id} "
                f"msg_id={message_id} operator={operator_id} user={user_id}"
            )

            # 艾特目标：执行撤回的人（若为空则艾特原发送者）
            at_target = operator_id or user_id
            if not at_target:
                logger.warning("[反撤回] 未找到撤回者 ID，放弃发送")
                return

            # 检查撤回者是否豁免（管理员/群主/白名单）
            try:
                exempt = await self._is_exempt(operator_id, group_id, event)
            except Exception as e:
                logger.warning(f"[反撤回] 豁免检查异常: {e}，默认不豁免")
                exempt = False
            if exempt:
                logger.info(
                    f"[反撤回] operator={operator_id} 在豁免名单中，跳过通知"
                )
                return

            # 从缓存中查找被撤回的消息
            cached = self._cache.get(group_id, {}).pop(message_id, None)

            # 清理过期缓存
            self._clean_expired(group_id)

            if cached:
                original_sender = cached["sender_name"] or "未知"
                original_content = cached["content"] or "[空消息]"

                logger.info(
                    f"[反撤回] 缓存命中，原发送者={original_sender}，"
                    f"内容预览={original_content[:50]}"
                )

                # 区分自己撤回和管理员代撤
                if operator_id and user_id and operator_id != user_id:
                    text = f" 撤回了 {original_sender} 的一条消息：\n{original_content}"
                else:
                    text = f" 撤回了自己的一条消息：\n{original_content}"

                chain = [Comp.At(qq=at_target), Comp.Plain(text)]
                try:
                    yield event.chain_result(chain)
                except Exception as e:
                    logger.error(f"[反撤回] 发送消息失败: {e}")

            else:
                logger.info("[反撤回] 缓存未命中，消息可能已过期")
                chain = [
                    Comp.At(qq=at_target),
                    Comp.Plain(" 刚刚撤回了条消息，但我没来得及记录 😢"),
                ]
                try:
                    yield event.chain_result(chain)
                except Exception as e:
                    logger.error(f"[反撤回] 发送消息失败: {e}")

    async def _is_exempt(
        self, operator_id: str, group_id: str, event: AstrMessageEvent
    ) -> bool:
        """判断撤回操作者是否应被豁免（不触发反撤回通知）。

        豁免条件（满足任一即豁免）：
        1. 在白名单中
        2. 是群主或管理员
        """
        if not operator_id or not group_id:
            return False

        # 条件 1：检查白名单
        if operator_id in self._whitelist:
            return True

        # 条件 2：检查是否为群主/管理员
        # 优先查缓存（消息事件已预缓存发送者角色，撤回时无需调 API）
        cached_role = self._role_cache.get(group_id, {}).get(operator_id)
        if cached_role:
            return cached_role in ("owner", "admin")

        # 缓存未命中，通过 OneBot API 查询（仅在用户从未发过消息时触发）
        try:
            if event.get_platform_name() != "aiocqhttp":
                return False

            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
                AiocqhttpMessageEvent,
            )

            if not isinstance(event, AiocqhttpMessageEvent):
                return False

            info = await event.bot.call_action(
                action="get_group_member_info",
                group_id=int(group_id),
                user_id=int(operator_id),
                no_cache=False,
            )
            role = str(info.get("role", "member"))
            self._role_cache[group_id][operator_id] = role

            logger.info(
                f"[反撤回] API 查询到 operator={operator_id} 的角色={role}"
            )
            return role in ("owner", "admin")

        except Exception as e:
            # API 调用失败（网络超时等），默认不豁免
            logger.warning(f"[反撤回] 获取群成员角色失败: {e}")
            return False

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

