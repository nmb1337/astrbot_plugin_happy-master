# astrbot_plugin_anti_recall

反撤回小助手 —— 群里有人撤回消息时，艾特那个人并把被撤回的消息重新发出来。

## 功能

- 🔍 自动缓存群聊消息（默认保留 10 分钟）
- 🚨 检测到撤回事件时，立即 @撤回者 并复读被撤回的内容
- 🧑‍🤝‍🧑 区分「自己撤回」与「管理员撤回他人消息」两种情况

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
            └── README.md
```

## 配置

插件开箱即用，无额外配置项。如需修改缓存时长，可编辑 `main.py` 中的 `self._cache_ttl` 变量（单位：秒，默认 600）。

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

