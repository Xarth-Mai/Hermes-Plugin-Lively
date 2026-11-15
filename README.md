# Hermes Lively

**让 Hermes 偶尔主动找你聊天，也能用本地表情包表达自己。**

Lively 是一个轻量级 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 插件。它沿用 Agent 原有的 SOUL、Memory、Skills、Cron 和 Gateway，不创建另一个人格，也不绑定微信或其他特定消息平台。

## 安装

**方式一 · 交给 Agent（推荐）**

把这句话发给你的 Hermes Agent：

> 按 https://github.com/Xarth-Mai/Hermes-Plugin-Lively/blob/main/INSTALL.md 安装 Lively。

Agent 会按 [首次安装指南](INSTALL.md) 检查插件并引导首次配置。仅安装不会开启主动联系。

**方式二 · 终端一行命令**

```bash
hermes plugins install Xarth-Mai/Hermes-Plugin-Lively --enable
```

根据 Hermes 的加载要求重启相关进程并开始新会话。安装后可让 Agent 按 [安装指南](INSTALL.md) 完成检查和配置。

## 能做什么

**自然主动联系** · 每 23 分钟由轻量脚本检查一次唤醒机会。只有满足免扰、冷却、频率上限和随机概率时才唤醒模型。Agent 再决定是否发言；没什么合适的话题，就保持沉默。

**逐渐适应你的节奏** · Agent 可以根据日常相处调整唤醒概率、冷却和免扰时段，也可以临时推迟下一次联系。硬性频率上限不会被自主调参突破。

**接得上的聊天** · 使用 Hermes 原生 `attach_to_session` 和 `continuity`，让主动消息进入聊天会话，并在后续定时运行中延续上一次有效输出。不会额外复制或存储聊天正文。

**有情境的表情包** · 本地图库按文件夹组织，每个文件夹都有 `metadata.json` 描述；支持 PNG、JPEG 和 GIF，使用 Hermes 的 `MEDIA:` 发送，不另做平台专用上传。

## 直接和 Agent 说

> 开启主动联系，偶尔来找我聊聊天

> 最近忙一点，晚上不要打扰我

> 这两天可以多来找我一点

> 暂停主动联系

> 找一张庆祝用的表情包

默认每天约 **1–2 次模型唤醒机会**，不是固定次数的消息。每次合格检查的概率为 15%，至少间隔 5 小时，滚动 24 小时最多 2 次、7 天最多 12 次，默认晚上 11 点至早上 8 点免扰。模型可自主选择不发言；频率是上限而非配额。

## 使用须知

- **需要明确授权**：安装后不会创建主动联系任务；只有你确认目标会话并同意后，Agent 才能使用 Hermes 原生 Cron 开启投递
- **消息平台由 Hermes 决定**：Lively 不依赖微信。只要 Hermes 的原生 Cron 能向该目标投递，就可以使用
- **原生能力有边界**：脚本自身完全无法运行时，部分 Hermes 版本仍可能唤醒模型；真实平台的图片呈现与会话续聊需要实机验收
- **普通聊天不受影响**：插件仅增加选择性主动联系与图库能力，不干预已有任务

高级配置、迁移与验证范围见 [安装指南](INSTALL.md)、[迁移说明](docs/migration.md) 和 [验证状态](docs/validation.md)。

## 许可证

代码采用 [MPL-2.0](LICENSE)。内置四张原创示例图采用 [CC0-1.0](assets/LICENSE.md)。
