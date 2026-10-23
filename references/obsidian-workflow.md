# Obsidian 周计划：数据契约与操作

本文件是「私人日程管理助手」与网页端（weekly-plan-viewer）共用的格式说明。
**两边读写同一份笔记，格式是唯一契约，改动会导致另一边读不到。**

## 一、笔记结构

```markdown
---
title: "第 1 周计划"
type: 周计划          # ← 必须。两边靠它筛选笔记
week: 1               # ← 必须，纯数字
start: 2026-10-19     # 推荐，周一
end: 2026-10-25       # 推荐，周日
cssclasses:
  - weekly-plan       # ← 触发 CSS 片段
tags:
  - 计划表
  - 周计划
---

> [!quote] 保持热爱，早睡早起。
> *Freedom is from within.*

# 第 1 周计划

**周期：** 2026-10-19（周一） → 2026-10-25（周日）

| 第 1 周计划 | 周一 | 周二 | 周三 | 周四 | 周五 | 周六 | 周日 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **5:00 - 5:30** | 起床 + 洗漱 |  |  |  |  |  |  |
| **第一节课** | 工作一<br>08:00 - 09:40 |  |  |  |  |  |  |
```

规则：

1. **表格是正文里的第一张表**，列固定为「时段 + 周一…周日」，共 8 列。
2. 第一列是时段名，用 `**加粗**` 包起来（不是强制，但保持统一）。
3. 单元格内换行写 `<br>`，不要写真实换行——真实换行会破坏表格。
4. 单元格里如果要写竖线 `|`，转义成 `\|`。
5. 时段行顺序决定网页端的配色分区（清晨 / 课程 / 午间 / 下午 / 傍晚 / 夜间 / 复盘 / 备注），所以**不要随意打乱行顺序**，否则颜色会串。

## 二、复盘批注区块

写在文件**末尾**，用 HTML 注释围栏标记，这样既能被程序可靠解析，在 Obsidian 里也只是普通表格，读起来自然：

```markdown
## 📝 复盘批注

<!-- weekly-plan:reviews v1 -->
| 位置 | 状态 | 批注 |
| :--- | :---: | :--- |
| 周一 · 5:00 - 5:30 | 未完成 | 昨晚刷手机到 1 点，赖床到 5:40 |
| 周二 · 第一节课 | 部分 | 被临时会议打断 |
<!-- /weekly-plan:reviews -->
```

- **位置**：`周几 · 时段名`。中间是 `空格+·+空格`。
- **状态**：只能是 `完成` / `部分` / `未完成`。留空表示只写批注、还没定性。
- **批注**：用户原话或简洁记录；换行写 `<br>`。
- 没有批注也没有状态的条目会被自动删除，不留空行。

## 三、踩过的坑（重要）

### 1. 只能解析"第一个连续的表格块"

早期实现是「扫描全文所有以 `|` 开头的行」。加了复盘区块之后就出问题了：
复盘表的表头 `| 位置 | 状态 | 批注 |` 和数据行 `| 周一 · 5:00 - 5:30 | 未完成 | … |`
都被当成了周计划的行。

**现象**：在网页上给一个任务打勾，表格最下面就会多出一行。
**根因**：复盘区多了一条记录 → 被误读成多了一行计划。
**修法**：遇到第一个非表格行（空行、标题、HTML 注释）就停止收集。

```python
def find_table_lines(lines):
    idx, started = [], False
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            idx.append(i); started = True
        elif started:
            break          # ← 关键
    return idx
```

### 2. 状态读写要保持同一套字面值

存进文件的是**中文**（`完成` / `部分` / `未完成`），因为用户要在 Obsidian 里直接读。
程序内部用 token（`done` / `partial` / `miss`）。
**读写两侧必须都做转换**，否则第二次写入会把中文覆盖成英文 token。

### 3. Obsidian 的「可读行宽」会挤窄表格

默认开启时内容区约 700px，而 8 列表格至少需要 1000px。
解决方式是在 CSS 片段里覆盖：

```css
.weekly-plan, .weekly-plan.markdown-preview-view, .weekly-plan .markdown-preview-view {
  --file-line-width: 1600px;
}
.weekly-plan .markdown-preview-sizer,
.weekly-plan .cm-sizer {
  max-width: none !important;
  width: 100% !important;
}
```

注意：`cssclasses` 在不同 Obsidian 版本里可能挂在阅读视图、编辑视图或外层容器上，
所以选择器要多写几组兜住。另外**不要**在 `.cm-sizer` 上加 `overflow-x`，
会干扰 CodeMirror 的滚动同步。

## 四、脚本用法

```bash
# 初始化目录、模板、CSS 片段
python3 scripts/obsidian_plan.py init-vault --vault "/path/to/Vault"

# 新建一周（--end 省略则自动 +6 天）
python3 scripts/obsidian_plan.py new-week --vault "/path/to/Vault" \
  --week 1 --start 2026-10-19

# 列出所有周
python3 scripts/obsidian_plan.py list-weeks --vault "/path/to/Vault" [--json]

# 查看某一周（--json 给程序用）
python3 scripts/obsidian_plan.py show-week --vault "/path/to/Vault" --week 1

# 写单元格
python3 scripts/obsidian_plan.py set-cell --vault "/path/to/Vault" \
  --week 1 --row "5:00 - 5:30" --day 周一 --value "起床 + 洗漱"

# 加行 / 删行
python3 scripts/obsidian_plan.py add-row --vault "/path/to/Vault" \
  --week 1 --label "午休" --after "12:00 - 13:40"
python3 scripts/obsidian_plan.py delete-row --vault "/path/to/Vault" \
  --week 1 --row "午休"

# 复盘
python3 scripts/obsidian_plan.py set-review --vault "/path/to/Vault" \
  --week 1 --row "5:00 - 5:30" --day 周一 \
  --status 未完成 --note "昨晚刷手机到 1 点，赖床到 5:40"
python3 scripts/obsidian_plan.py list-reviews --vault "/path/to/Vault" --week 1
```

参数约定：

| 参数 | 说明 |
| --- | --- |
| `--day` | `周一`…`周日` 或 `1`…`7` |
| `--status` | `完成` / `部分` / `未完成` / `清除`；也接受 `done` / `partial` / `miss` |
| `--note` | 省略则保留原有批注 |
| `--folder` | 默认 `日程规划` |
| `--force` | `init-vault` / `new-week` 时覆盖已存在文件 |

## 五、备份

每次写入前自动备份到 `<计划目录>/.weekly-plan-backups/`，文件名带时间戳，最多保留 40 份。
写入采用「写临时文件 → 原子替换」，中途失败不会损坏原文件。

## 六、排错速查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 网页底部多出「位置」行 | 解析器扫了全文 | 确认用的是"只取第一个连续表格块"的版本 |
| 表格很窄 | 可读行宽限制 | 启用 CSS 片段（含 `--file-line-width` 覆盖） |
| 写不进去 | frontmatter 不对 | 检查 `type: 周计划`、`week` 为纯数字 |
| 找不到行名 | `--row` 和表里不一致 | 先 `show-week` 看准确行名 |
| 颜色串了 | 行顺序被改动 | 恢复标准时段顺序 |
| 状态变成英文 | 读写转换不对称 | 存中文、内部用 token，两侧都要转换 |
