# astrbot_plugin_anti_recall

反撤回小助手 —— 群里有人撤回消息时，艾特那个人并把被撤回的消息重新发出来。

## 功能

- 🔍 自动缓存群聊消息（默认保留 10 分钟）
- 🚨 检测到撤回事件时，立即 @撤回者 并复读被撤回的内容
- 🧑‍🤝‍🧑 区分「自己撤回」与「管理员撤回他人消息」两种情况
- 🛡️ **群主和管理员撤回消息不会被复读**（默认豁免）
- 📋 支持白名单配置，白名单内用户撤回也不复读

## 支持的平台

- `aiocqhttp`（OneBot v11，如 NapCat / Lagrange）

## 安装

将插件文件夹放入 AstrBot 的 `data/plugins/` 目录下，在 WebUI 插件管理中启用即可。

```
AstrBot/
└── data/
    └── plugins/
        └── astrbot_plugin_anti_recall/
            ├── main.py
            ├── metadata.yaml
            ├── _conf_schema.json
            └── README.md
```

## 配置

在 WebUI → 插件管理 → 反撤回小助手 → 配置中，可设置以下选项：

```json
{
    "group_whitelist": ["123456789"],
    "whitelist": ["987654321"]
}
```

| 配置项 | 说明 |
|--------|------|
| `group_whitelist` | **群白名单**（群号）。只有列表内的群才启用反撤回。留空 `[]` 表示所有群都生效 |
| `whitelist` | **用户白名单**（QQ号）。白名单内用户撤回消息不会被复读。群主和管理员默认豁免，无需添加 |

如需修改缓存时长，可编辑 `main.py` 中的 `self._cache_ttl` 变量（单位：秒，默认 600）。

## 豁免规则

| 撤回者身份 | 撤回自己消息 | 撤回他人消息 |
|-----------|-------------|-------------|
| 普通群员 | ✅ 复读 | ✅ 复读 |
| 白名单用户 | ❌ 不复读 | ❌ 不复读 |
| 管理员 | ❌ 不复读 | ❌ 不复读 |
| 群主 | ❌ 不复读 | ❌ 不复读 |

## 效果示例

```
[群聊]
用户A: 今天天气真好
用户A 撤回了 用户A 的一条消息

Bot: @用户A 撤回了自己的一条消息：
今天天气真好
```

## 依赖

无额外依赖，仅使用 AstrBot 内置 API。

## 相关链接

- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot 项目](https://github.com/AstrBotDevs/AstrBot)

- [AstrBot 项目](https://github.com/AstrBotDevs/AstrBot)

