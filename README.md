# Hermes Lively

为 Hermes 添加适度的主动联系和本地表情包。沿用现有 SOUL、Memory、Skills、Cron 和 Gateway；
不另起 Agent，不改写人格文件，不接管编程任务。

**当前状态：v0.1.0 开发实现，尚未发布验收。** 自动测试和固定 Hermes 契约检查已完成；
真实微信 iLink 收图、主动联系及续聊仍需登录环境验收，不能视为已验证可上线。
详见 [验证记录](docs/validation.md) 和 [NianYu 参考说明](docs/nianyu-reference.md)。

## 安装

代码进入 GitHub 仓库后，使用 Hermes 原生命令：

```bash
hermes plugins install Xarth-Mai/Hermes-Plugin-Lively --enable
```

安装后重启需要重新加载插件的 Hermes 进程，并开始新会话，使工具与常驻提示完整生效。
安装即提供四张原创示例和图库管理；**不会创建主动联系 Cron，也不会主动联系任何人**。
代码只有 Python 标准库和 Hermes 已提供的能力；Pillow 仅在重新绘制示例素材时需要。

**请自行关闭 Cron 消息包装。** 在当前 Profile 的 `$HERMES_HOME/config.yaml` 中，把下列
设置合并到已有的 `cron` 段落，避免重复 YAML 键：

```yaml
cron:
  wrap_response: false
```

此设置影响该 Profile 的**全部 Cron 任务**。插件不自动修改它。Lively 的自然消息以关闭包装
后的效果设计和验收；保留默认值仍可运行，但消息会带 `Cronjob Response` 标题和任务说明。

**如果由 Agent 代为安装，Agent 也必须提醒用户自行关闭包装，说明全局影响，并报告当前状态。**
可直接给安装 Agent 以下指令：

> 安装并启用 Xarth-Mai/Hermes-Plugin-Lively，验证两个工具和两份插件 Skill，报告安装状态。
> 在我明确授权微信私聊目标前，保持主动联系关闭。检查当前 Profile 的 cron.wrap_response；
> 若未关闭，提醒我自行设为 false，并说明这影响该 Profile 的所有 Cron；不要代我静默改动。
> 若已关闭，请说明当前状态。不要修改 SOUL、USER 或 MEMORY。

## 微信 iLink 与启用主动联系

本版首先适配 Hermes 内置 **Weixin / WeChat** 平台，即腾讯 iLink Bot API，不是企业微信。
按 [Hermes 微信接入说明](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/weixin)
运行 `hermes gateway setup`，选择 Weixin，完成扫码并启动 Gateway。
建议个人专用 Profile 配合微信用户 allowlist；Lively 不是共享机器上的独立账户权限系统。

先从微信向 Hermes 发一条私聊，让插件观察到可信目标。然后可以说：

> 开启主动联系，偶尔找我聊天，发到当前微信私聊，晚上 23 点到早上 8 点不要打扰。

Agent 按以下协议操作：

1. `lively_contact(status)` 查看目标；`configure` 设置频率和免扰。
2. 用户明确授权后，`prepare(destination="weixin:<chat_id>", authorized=true)` 返回原生 Cron 参数。
3. 先暂停返回的旧任务（如果有），再按返回参数**暂停创建**新任务；回读真实任务 ID 与字段。
4. `activate(job_id=...)` 验证绑定，再由原生 Cron 恢复任务。
5. `diagnose` 确认任务启用；任何环节失败，先 `disable`，再暂停对应任务。

每个 Profile 只支持一个明确授权的微信私聊目标。CLI/TUI/Desktop 也能管理，但必须选择已观察到
的微信目标。不支持 `all`、群聊或自动切换渠道。本版主动联系以 `plugins.isolation: in_process`
验证；若你启用了 `host` 隔离，`prepare` 会拒绝启用，不会替你更改全局隔离设置。

| 频率 | 最短尝试间隔 | 滚动尝试上限 |
| --- | --- | --- |
| occasional（默认） | 48 小时 | 七日 2 次 |
| regular | 24 小时 | 七日 4 次 |
| clingy | 12 小时 | 24 小时 1 次 |

所有档位还需满足：至少两小时无用户活动、不在免扰时段、没有正在执行或待处理的工作、
目标与账号绑定有效。Cron 每 30 分钟检查一次，不合格的检查不调用模型。

频率是硬上限，不是必须发送的目标。普通问候、好奇或分享想法都可以成为表达理由；Agent
仍可只返回 `[SILENT]`。已放行机会无论静默或失败都计入尝试预算；连续未回应机会延长冷却，
最长七日。绑定用户的可信微信回应清零连续计数，但不返还滚动预算。
“未回应机会”不是“已送达但未回复的消息数”，不推断已读、忽略或人际态度。

暂停时说“暂停主动联系”：先调用插件 `disable` 撤销资格，再用原生 Cron 暂停返回的任务 ID。

## 工具和配置

| 工具 | 动作 |
| --- | --- |
| `lively_contact` | `status`、`configure`、`prepare`、`activate`、`disable`、`diagnose` |
| `lively_stickers` | `status`、`list`、`search`、`import`、`remove` |

工具输入为 JSON，结果为 JSON 字符串，包含 `ok` 及数据或可操作的错误说明。
Skill 可通过 `skill_view("lively:proactive-contact")`、`skill_view("lively:sticker-gallery")` 加载，
并由当前基线的 Hermes 列入可用技能。行为提示只在新会话生效。

配置位于 `plugins.entries.lively.settings`，参见 [配置示例](config.example.yaml)。
`configure(settings=...)` 可修改频率、免扰和 `stickers_enabled`；主动联系开关必须通过启用协议
或 `disable` 修改。直接把 `proactive_enabled` 写成 true 不会建立授权或创建任务。
免扰使用 Profile 本地时间；支持跨午夜，起止相同无效，关闭须设 `quiet_hours_enabled: false`。

状态报告配置、目标、任务 ID、活动与尝试时间、跳过原因及下一次可能触发时间的下界。
下界不承诺发送，免扰、工作、平台状态和自主静默都可能继续延后。

## 表情包

内置 greeting、happy、confused、comfort 四张原创 Lumi 示例，均为不透明 192×192 RGB PNG。
检索匹配标签与描述，支持中文标签；通常每回合最多一张，遵守用户反馈，不在编程任务中强行插图。

```json
{"action":"search","query":"开心 庆祝","limit":3}
```

`lively_stickers` 返回经过校验的 `absolute_path`。Agent 在正常回复中单独一行使用
`MEDIA:/absolute/path`，由 Hermes Gateway 发送；没有第二套上传接口。

```json
{"action":"import","path":"/absolute/path/my-image.png","description":"开心的小猫","tags":["开心","猫"]}
```

个人素材支持 PNG、JPEG、GIF，单张最多 10 MiB。导入复制到个人图库，按内容去重；拒绝链接、
路径逃逸、扩展名与文件头不符和超限文件。`remove(id=...)` 只删除个人素材。
`stickers_enabled=false` 停止自动建议；用户明确查看或检索时可传 `explicit=true`，仍可管理图库。

## 数据、更新与卸载

配置跟随当前 Profile。数据库与个人图库存于 `ctx.state.data_dir`，不假定其目录名等于 lively。
只记录必要标识、时间、机会记录和图库元信息，不另存聊天正文或微信 token。

预检副本放在 `$HERMES_HOME/scripts/lively-preflight-<binding-id>.py`。每次重新准备使用独立路径，
防止旧 Cron 在新绑定下恢复资格。脚本校验安装身份、版本/内容哈希、配置、任务、账号、工作占用
和原子机会领取；安装身份文件 `.lively-install-id` 不进入 Git。

```bash
hermes plugins update lively
hermes plugins disable lively
hermes plugins remove lively
```

更新保留个人数据和设置；若安装身份或预检版本发生变化，重新授权、prepare 并回读任务。
禁用、移除和身份改变后，旧脚本会静默跳过。已开始的原生模型运行不承诺被卸载立即取消。
建议卸载前先 `disable`，暂停/取消在途 Lively Cron，再移除插件。不要手工删除整个 scripts 目录。

原生卸载可能留下暂停或不可放行的任务与脚本。用 `hermes cron list` 找出并核对插件返回的 Job ID，
通过 `hermes cron --help` 对应的原生管理命令删除该任务；确认没有任务引用后，才删除对应
`lively-preflight-<binding-id>.py`。不批量删除同名或其他 Cron。重装不会自动继承旧授权。

## 开发与支持边界

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python scripts/validate-assets.py
# Hermes 源码必须放在插件目录之外，并切到下述固定提交
python -m pip install -r tests/requirements-hermes.txt
python scripts/check-hermes.py --source ../hermes-agent
```

基线：Hermes `bfe20f5586b3a26259f71669ad49ac85bd173f10`，Python ≥3.11。
本地验证 Python 3.12；CI 配置测试 3.11/3.12/3.13，不等于所有矩阵任务已经在 GitHub 执行。
契约检查禁用网络，验证实际注册、原生 Cron、脚本门控和工作租约；不用假模型冒充微信实测。

微信 context token、过期降级、CDN 和账号连接由宿主管理。文字 ACK 不证明图片实际到达；
未知投递不自动补发。`attach_to_session` 已绑定到任务，但真实微信续聊仍待验收。
没有官方发送前阻断能力时，新用户消息或停用可能在预检之后到达；此竞态不能仅靠提示词消除。
模型错误通知使用任务级 `failure_deliver: local`，不向微信投递运行错误提醒。

代码 MPL-2.0；内置 PNG 单独采用 CC0-1.0，见 [素材授权](assets/LICENSE.md)。
