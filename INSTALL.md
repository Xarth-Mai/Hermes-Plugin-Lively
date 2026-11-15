# Lively · Agent 首次安装指南

> 这份文档供 Hermes Agent **安装前**阅读。安装完毕后，日常行为由 `lively:proactive-contact` 与 `lively:sticker-gallery` 两份 Skill 负责。

## 目标与边界

安装并验证 [Hermes Lively](https://github.com/Xarth-Mai/Hermes-Plugin-Lively)，在用户单独明确授权后，才为指定会话开启主动联系。保持现有 SOUL、USER、Memory、聊天通道与其他 Cron 不变。**不要修改 Hermes 源码。**

安装插件和授权主动联系是两回事。仅收到“安装”请求时，检查成功后告知用户可以如何启用，不得自行创建或恢复主动投递任务。

## 1. 安装与检查

1. 检查当前 Hermes Profile 是否已安装 `lively`。已存在时先确认版本，不重复安装；如仍是 v0.1 的微信专用实现，确认是否需要升级或迁移。
2. 使用原生命令：

   ```bash
   hermes plugins install Xarth-Mai/Hermes-Plugin-Lively --enable
   ```

3. 按 Hermes 当前版本要求重载插件并开始新会话，检查 `lively_schedule`、`lively_stickers` 和两份 Skill 是否注册。需要时显式加载 `skill_view("lively:proactive-contact")` 与 `skill_view("lively:sticker-gallery")`。注册成功不等于旧会话已经获得新提示。
4. 确认插件版本至少为 `0.2.0`、当前 Profile 的 Python ≥3.11，并检查插件状态。如果版本或工具不符合文档，使用真实安装版本的能力，勿假装新功能可用。

## 2. 首次引导

简短告诉用户：Lively 可以偶尔主动聊天并使用本地表情包；主动联系默认关闭；随机唤醒不会保证每次发言；用户可以随时暂停或调整节奏。

仅在用户尚未授权时问一句：“要开启主动联系，并发到我们现在的私聊吗？”

如果是在 CLI/TUI/Desktop 等没有可靠消息来源的环境，让用户明确选择 Hermes 已配置并支持投递的会话目标。不要猜测 ID，也不要使用群发目标 `all`。

## 3. 用户明确授权后配置 Cron

1. 读取当前 Profile 的 Cron 列表。若存在旧版 `lively-proactive` / `lively-preflight-*` 任务，**先暂停旧任务并记录 ID**，避免两个任务并行。不要直接删除用户其他 Cron。
2. 调用 `lively_schedule(action="prepare")`。它初始化 Profile 数据文件并安装稳定的 `scripts/lively-gate.py`；返回的原生 Cron `script` 参数是 **`lively-gate.py`**，不是绝对路径。
3. 使用 `lively_schedule(action="status")` 核实设置。插件默认值：每 23 分钟检查、合格检查 15% 唤醒概率、5 小时冷却、滚动 24 小时最多 2 次、7 天最多 12 次、当地晚上 11 点到早上 8 点免扰。它们是**唤醒机会**而非保证发送的消息次数；静默也消耗额度。
4. 使用用户明确选择的、Hermes 原生支持的私聊投递目标，创建唯一的任务。若当前消息来源可靠并且用户明确同意发到此处，可用 `deliver=origin`；否则必须使用已验证的原生目标，不得猜测。

   原生 `cronjob_manage` 任务参数：

   ```yaml
   name: lively-proactive
   schedule: 23m
   script: lively-gate.py
   skills: [lively:proactive-contact]
   prompt: "Load lively:proactive-contact. Speak naturally when appropriate or return [SILENT]."
   deliver: origin     # 仅在确认当前私聊来源有效时使用；否则填已核实目标
   attach_to_session: true
   continuity: true
   failure_deliver: local
   catch_up: false
   paused: true
   ```

5. 在支持任务级 `wrap_response` 的 Hermes 中，再为此任务设置 `wrap_response: off`。旧版仅有 Profile 级 `cron.wrap_response: false`，它影响当前 Profile **所有 Cron**；必须说明影响并征得用户同意才可修改，用户不同意就保留包装文本。
6. 创建后回读真实 Job ID、目标、脚本路径、参数与暂停状态；检查无重复任务后恢复该任务，再回读确认。如果设置或恢复失败，暂停该任务并报告问题，不声称已启用。

**上下文区别**：`attach_to_session: true` 使主动回复写入目标聊天的会话历史；`continuity: true` 把当前 Cron 上一次非静默输出提供给下一次运行。它们不自动读取任意渠道的完整聊天记录。`catch_up: false` 防止 Gateway 重启后补跑过期机会；`failure_deliver: local` 避免把运行错误发送给用户。

## 可选：多个 Profile 共用图库（0.2.1+）

由所有者指定一个真实的共享目录，为每个 Profile 的 `ctx.state.data_dir / "gallery"` 创建指向该目录的软链接（先从原生 PluginContext 取得 data_dir，不要猜测命名空间；新版 Hermes 可能使用 `plugin-data/agent-plugin-lively-<hash>/`），然后使用原生配置命令设置：

```bash
hermes --profile <profile> config set plugins.entries.lively.settings.shared_gallery /absolute/shared/gallery
```

共享目录及其父目录必须是真实目录；Profile 的 gallery 必须是指向该精确目录的软链接。只有显式设置此项才接受图库根链接，图片、分类目录和 metadata 的软链接仍被拒绝。图库写操作使用共享目录的 `.lively-state` 锁，主动联系的设置、配额与记录仍各归自己的 Profile。导入、删除对所有共用者生效，应先确认图库所有者的授权；这不授权跨 Profile 读取聊天或自动投递。不要把私人图库提交到插件仓库。

## 4. 日常使用

Agent 可以在适当的时候调用 `lively_schedule(action="tune", settings={...})` 调节 `wake_probability`、`cooldown_hours`、`quiet_hours`，或用 `next_probability` / `snooze_until` 调节下一次机会。概率 0–1，冷却 4–168 小时；`snooze_until` 是未来 30 天内的 Unix 时间戳或 null。临时概率直到下一次成功唤醒后才清除。

**滚动 24 小时和 7 天的硬上限不是 Agent 自主可调参数。** 用户希望修改限量时，说明这是高级配置，需由 Profile 所有者修改配置文件并确认。不要因为连续没有回复而推断用户忽略了自己。

暂停或关闭主动联系时，使用原生 Cron 暂停/移除准确的 Lively Job ID。插件禁用或卸载之前也要先暂停 Cron，确认无其他任务引用其脚本，再选择是否移除管理脚本。个人图库和配置不要自动删除。

## 5. 版本迁移和失败边界

首次访问新图库时，旧版 `gallery/manifest.json` 的个人导入图会复制到 `gallery/legacy/`，原文件仍保留以便回滚。旧版 `data.db` 不自动删除，原有联系方式和授权也**不自动继承**。详见 [迁移说明](docs/migration.md)。

轻量脚本对 Python 运行时异常尽量输出 `{"wakeAgent":false}`。但 Hermes 部分版本对**脚本未执行/输出无效**采取默认唤醒，无法在不修改 Hermes 的前提下绝对消除；这不是插件权限或限量的严格安全边界。不要为解决这个问题擅自改 Hermes。

## 6. 完成后向用户报告

只报告真实检查过的：插件版本、两工具与 Skill、主动联系是否开启、具体投递目标、Cron 唯一性与状态、`attach_to_session`、`continuity`、`catch_up`、消息包装、默认频率和暂停方法。

不得为了验收而在未经同意时试发。无法真实验证平台图片或会话续聊时，说明仍待实机验证。答复要简短自然，避免抛出所有技术参数让用户选择。
