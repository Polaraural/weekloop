# 安装与使用说明

## 已安装位置

Skill 已安装到：

```text
~/.codex/skills/私人日程管理助手/
```

包含：

```text
SKILL.md                              工作流和使用规则
agents/openai.yaml                    Skill 显示信息
scripts/obsidian_plan.py              读写 Obsidian 周计划表与复盘批注
scripts/apple_scheduler.py            写 Apple 日历/提醒事项、回读、附图、幂等更新
scripts/extract_chat_archive.py       解压聊天记录并生成 manifest.json
scripts/install_helper.py             安装 WorkBuddy 用的独立 Helper
scripts/check_permissions.py          检查日历/提醒事项/辅助功能权限
references/install-and-usage.md       本说明
references/obsidian-workflow.md       Obsidian 数据契约与排错
references/review-workflow.md         对话式复盘的流程与提问脚本
```

Codex 会在相关请求出现时自动发现它。也可以显式调用：

```text
$私人日程管理助手 分析这份聊天记录：固定时间的安排写成 Obsidian 周计划表，
有约见的放进 Apple 日历，要做的动作放进提醒事项。相关图片作为附件。
```

也可以只走其中一条通道：

```text
$私人日程管理助手 帮我把这周排成 Obsidian 周计划表。
$私人日程管理助手 我想复盘这周，陪我一条条过一下。
```

## 权限准备

首次使用前，在 Mac 上完成以下授权：

1. 打开“系统设置 > 隐私与安全性 > 日历”，允许 Codex 或运行脚本的终端访问日历。
2. 打开“系统设置 > 隐私与安全性 > 提醒事项”，允许 Codex 或运行脚本的终端访问提醒事项。
3. 打开“系统设置 > 隐私与安全性 > 辅助功能”，允许 Codex 或运行脚本的终端控制电脑。
4. 确认 Mac 已登录 iCloud，并开启“日历”和“提醒事项”同步，否则手机端可能看不到图片附件。

没有辅助功能权限时，文字、日期和备注仍可能写入，但图片附件无法可靠自动添加。脚本不会用路径文字冒充附件；遇到权限错误应停止并提示授权。

## 推荐调用方式

把聊天记录 ZIP 或截图交给任意 Codex agent，并说明：

```text
使用 wechat-apple-scheduler 分析这个聊天记录。
把明确属于我的日程写入 Apple 日历，把待办写入提醒事项；
有歧义的日期、参加状态或时间先问我。
图片要作为对应事项的原生附件，不要写成路径。
写完后回读核对，并检查不要重复。
```

如果希望批量自动化，可增加：

```text
明确属于我的事项直接写入；不确定的放入“待确认清单”等我确认。
不需要每次预览，但改期、取消和删除已有事项前必须先问我。
```

## Obsidian 周计划

### 初始化

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/obsidian_plan.py init-vault \
  --vault "/path/to/YourVault"
```

会建子目录 `日程规划/`、写模板与索引、写入并启用 CSS 片段 `weekly-plan`。

### 建周与填写

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/obsidian_plan.py new-week \
  --vault "/path/to/YourVault" --week 1 --start 2026-10-19

python3 ~/.codex/skills/私人日程管理助手/scripts/obsidian_plan.py set-cell \
  --vault "/path/to/YourVault" --week 1 --row "5:00 - 5:30" --day 周一 \
  --value "起床 + 洗漱"
```

`--day` 可用 `周一`…`周日` 或 `1`…`7`。

### 复盘

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/obsidian_plan.py set-review \
  --vault "/path/to/YourVault" --week 1 --row "5:00 - 5:30" --day 周一 \
  --status 未完成 --note "昨晚刷手机到 1 点，赖床到 5:40"

python3 ~/.codex/skills/私人日程管理助手/scripts/obsidian_plan.py list-reviews \
  --vault "/path/to/YourVault" --week 1
```

数据格式、字段约定和排错见 `references/obsidian-workflow.md`；
对话式复盘该怎么问、怎么记，见 `references/review-workflow.md`。

### 表格显示很窄？

Obsidian 默认开启「可读行宽」，内容区约 700px，而周计划表有 8 列。
`init-vault` 写入的 CSS 片段已经覆盖了宽度限制。如果仍很窄，检查
「设置 → 外观 → CSS 片段」里 `weekly-plan` 是否启用。

## 手动执行脚本

### 1. 解压聊天记录

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/extract_chat_archive.py \
  "/absolute/path/to/chat.zip" \
  --output "/absolute/path/to/workdir"
```

生成的 `manifest.json` 会列出文本、图片和文件路径。随后用视觉能力分析图片，不要只看文件名。

### 2. 创建或更新提醒事项

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/apple_scheduler.py upsert-reminder \
  --state "$HOME/.codex/state/wechat-apple-scheduler.json" \
  --key "source-date-parcel" \
  --list "聊天日程试运行" \
  --title "📦 出门拿快递" \
  --body "菜鸟驿站：合肥新华御湖上园北门105店" \
  --date 2026-10-03
```

需要具体通知时间时加：

```bash
--time 08:00
```

### 3. 创建或更新日历事件

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/apple_scheduler.py upsert-event \
  --state "$HOME/.codex/state/wechat-apple-scheduler.json" \
  --key "source-date-guest" \
  --calendar "聊天日程试运行" \
  --title "🏡 朋友来做客" \
  --body "预计16:00–17:00到达；不是聚会结束时间。" \
  --date 2026-10-03 \
  --start-time 16:00 \
  --end-time 17:00 \
  --alert-minutes 0
```

没有具体时间时使用 `--all-day`。每日重复事件加 `--repeat daily`。

### 4. 添加图片附件

提醒事项：

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/apple_scheduler.py attach-reminder-image \
  --list "聊天日程试运行" \
  --reminder-id "<reminder-id>" \
  --image "/absolute/path/image.jpg"
```

日历：

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/apple_scheduler.py attach-event-image \
  --calendar "聊天日程试运行" \
  --event-uid "<event-uid>" \
  --image "/absolute/path/image.jpg"
```

脚本默认会防重复，返回 `already-attached` 时不要再次粘贴；只有明确要求重贴时才加 `--force`。

### 5. 回读验证

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/apple_scheduler.py list-reminders \
  --list "聊天日程试运行"

python3 ~/.codex/skills/私人日程管理助手/scripts/apple_scheduler.py list-events \
  --calendar "聊天日程试运行"
```

验证日期、时间、全天状态、通知、附件、完成状态和原生 ID。

## 每日 09:00／21:00 规划提醒

首次创建：

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/apple_scheduler.py upsert-event \
  --state "$HOME/.codex/state/wechat-apple-scheduler.json" \
  --key "daily-morning" --calendar "聊天日程试运行" \
  --title "☀️ 规划今天" \
  --body "看看日程和待办，选出今天最重要的三件事。" \
  --date 2026-10-03 --start-time 09:00 --end-time 09:10 \
  --repeat daily --alert-minutes 0

python3 ~/.codex/skills/私人日程管理助手/scripts/apple_scheduler.py upsert-event \
  --state "$HOME/.codex/state/wechat-apple-scheduler.json" \
  --key "daily-evening" --calendar "聊天日程试运行" \
  --title "🌙 复盘今天，安排明天" \
  --body "回顾完成情况，处理未完成事项，预排明天。" \
  --date 2026-10-03 --start-time 21:00 --end-time 21:10 \
  --repeat daily --alert-minutes 0
```

它们只是日历提醒，不会自动读取新聊天。要自动读取新记录，需要另设定时导入或每次手动把新记录交给 agent。

## 日常使用建议

- 每次给新聊天记录时说明“这是新记录还是完整替换”。
- 对“明天”“周五”等相对日期，以消息发送时间为基准；用户后续纠正优先。
- 对邀请、海报和转发内容，先确认是否真的要参加。
- 需要改期、取消、删除时，给出事件标题和日期，不要只说“那个”。
- 同一事项分批更新时保留相同 `--key`，让脚本更新原对象而不是新建。

## 卸载

```bash
rm -rf ~/.codex/skills/私人日程管理助手
```

状态文件默认位于：

```text
~/.codex/state/wechat-apple-scheduler.json
```

删除它不会删除 Apple 日历或提醒事项里的原对象，只会让后续脚本失去原生 ID 映射。需要清理 Apple 数据时，应在应用中逐项确认删除。

## WorkBuddy 专用：独立 Helper

WorkBuddy 缺少 Apple Events 权限时，直接 `osascript` 会失败。解决方式是安装独立 Helper app，让 Helper 成为 TCC 责任进程：

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/install_helper.py
```

默认安装路径：

```text
~/Applications/Apple Chat Scheduler Helper.app
```

首次授权与自检：

```bash
python3 ~/.codex/skills/私人日程管理助手/scripts/check_permissions.py
```

如果 macOS 弹出“Apple Chat Scheduler Helper 想要控制提醒事项/日历”时选择允许。若日历仍报 `-1743`，到“系统设置 > 隐私与安全性 > 自动化”，给 `Apple Chat Scheduler Helper` 勾选“日历”和“提醒事项”。然后到：

```text
系统设置 > 隐私与安全性 > 辅助功能
```

把下面的 app 加入并勾选：

```text
~/Applications/Apple Chat Scheduler Helper.app
```

之后 WorkBuddy 中再次使用 skill 时，脚本会自动检测 WorkBuddy，并把任务写到固定文件：

```text
~/Library/Application Support/AppleChatScheduler/job.json
```

随后用 `open -n <Helper>` 启动 Helper。脚本不再使用 `open --args` 传参，因为某些 macOS/open 组合会静默丢弃参数。

WorkBuddy 只负责启动 Helper，不需要 WorkBuddy 自己拥有 Apple Events 权限。Helper 内部通过 `/usr/bin/osascript` 子进程执行 AppleScript；本机测试中，这条通道比 Helper 直接 `NSAppleScript` 更可靠。

如果重新运行 `install_helper.py` 或修改 Helper，ad-hoc 签名会变化，可能需要重新授权。
