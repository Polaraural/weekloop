#!/usr/bin/env python3
"""私人日程管理助手 — Obsidian 周计划读写

与网页端（weekly-plan-viewer）使用完全相同的 Markdown 约定，
两边可以安全地读写同一份笔记。

约定：
  * 周计划是一张 Markdown 表格，写在笔记正文里。
  * 复盘批注写在文末受控区块内，用 HTML 注释做围栏：

        ## 📝 复盘批注

        <!-- weekly-plan:reviews v1 -->
        | 位置 | 状态 | 批注 |
        | :--- | :---: | :--- |
        | 周一 · 5:00 - 5:30 | 未完成 | 赖床到 5:40 |
        <!-- /weekly-plan:reviews -->

  * 只解析文件里"第一个连续的表格块"，因此复盘表不会被误当成计划行。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

REVIEW_HEADING = "## 📝 复盘批注"
REVIEW_START = "<!-- weekly-plan:reviews v1 -->"
REVIEW_END = "<!-- /weekly-plan:reviews -->"

STATUS_TO_CN = {"done": "完成", "partial": "部分", "miss": "未完成"}
CN_TO_STATUS = {v: k for k, v in STATUS_TO_CN.items()}

DEFAULT_ROWS = [
    "5:00 - 5:30", "5:40 - 6:00", "6:10 - 7:10",
    "第一节课", "第二节课", "12:00 - 13:40",
    "第三节课", "第四节课", "5:40 - 6:40",
    "19:00 - 20:00", "20:10 - 20:30", "20:40 - 21:40",
    "22:00 - 22:55", "23:00 - 23:20", "23:20 - 23:30",
    "计划完成情况", "学习情况", "体育情况", "备注",
    "", "", "",
]

LEGEND = (
    '<span class="wp-legend morning">清晨</span> '
    '<span class="wp-legend class">课程</span> '
    '<span class="wp-legend noon">午间</span> '
    '<span class="wp-legend afternoon">下午课程</span> '
    '<span class="wp-legend evening">运动 / 傍晚</span> '
    '<span class="wp-legend night">夜间</span> '
    '<span class="wp-legend review">复盘</span> '
    '<span class="wp-legend notes">备注</span>'
)

SPLIT_RE = re.compile(r"(?<!\\)\|")


# ---------------------------------------------------------------- 基础解析
def parse_frontmatter(text: str) -> tuple[dict, int]:
    """返回 (frontmatter 字典, 正文起始下标)。"""
    if not text.startswith("---"):
        return {}, 0
    end = text.find("\n---", 3)
    if end == -1:
        return {}, 0
    raw = text[3:end].strip()
    fm: dict[str, str] = {}
    for line in raw.split("\n"):
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if not m:
            continue
        v = m.group(2).strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        fm[m.group(1)] = v
    return fm, end + 4


def find_table_lines(lines: list[str]) -> list[int]:
    """文件里第一个连续的表格块（遇到非表格行就停）。"""
    idx: list[int] = []
    started = False
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            idx.append(i)
            started = True
        elif started:
            break
    return idx


def parse_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in SPLIT_RE.split(s)]


def is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells)


def split_table_line(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in SPLIT_RE.split(s)]


def build_table_line(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def normalize_value(v) -> str:
    s = str(v if v is not None else "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", "<br>")
    s = re.sub(r"(?<!\\)\|", r"\\|", s)
    return s.strip()


def strip_stars(s) -> str:
    return re.sub(r"^\s*\*\*|\*\*\s*$", "", str(s if s is not None else "")).strip()


def day_index(token) -> int:
    """接受 周一..周日 / 1..7 / 0..6（0 也被当作周一）。"""
    t = str(token).strip()
    if t in WEEKDAYS:
        return WEEKDAYS.index(t)
    if t.isdigit():
        n = int(t)
        if 1 <= n <= 7:
            return n - 1
    raise ValueError(f"无法识别的星期：{token}（可用 周一..周日 或 1..7）")


# ---------------------------------------------------------------- 周表解析
def parse_week_text(text: str) -> dict | None:
    lines = text.split("\n")
    idx = find_table_lines(lines)
    if len(idx) < 3:
        return None
    parsed = [parse_row(lines[i]) for i in idx]
    header = parsed[0]
    start_i = 1
    if len(parsed) > 1 and is_separator(parsed[1]):
        start_i = 2

    days = [(header[i + 1] if i + 1 < len(header) and header[i + 1] else WEEKDAYS[i]) for i in range(7)]

    rows = []
    for i in range(start_i, len(parsed)):
        cells = parsed[i]
        if is_separator(cells):
            continue
        raw_label = cells[0] if cells else ""
        label = strip_stars(raw_label)
        values = [(cells[j + 1] if j + 1 < len(cells) else "") for j in range(7)]
        rows.append({"line": idx[i], "label": label, "raw_label": raw_label, "values": values})
    return {"days": days, "rows": rows, "table_start": idx[0], "table_end": idx[-1]}


# ---------------------------------------------------------------- 复盘区块
def review_rows_from(text: str) -> list[dict]:
    start = text.find(REVIEW_START)
    if start == -1:
        return []
    end = text.find(REVIEW_END, start)
    if end == -1:
        return []
    block = text[start + len(REVIEW_START):end]
    rows, seen_header = [], False
    for line in block.split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = parse_row(line)
        if is_separator(cells):
            continue
        if not seen_header:
            seen_header = True
            continue
        if len(cells) < 2 or not cells[0].strip():
            continue
        raw_status = cells[1].strip()
        status_cn = STATUS_TO_CN.get(raw_status, raw_status if raw_status in CN_TO_STATUS else "")
        note = cells[2] if len(cells) > 2 else ""
        note = re.sub(r"\s*<br\s*/?>\s*", "\n", note, flags=re.I).replace("\\|", "|").strip()
        rows.append({"key": cells[0].strip(), "status_cn": status_cn, "note": note})
    return rows


def parse_reviews(text: str) -> dict:
    out = {}
    for r in review_rows_from(text):
        m = re.match(r"^(.+?)\s*·\s*(.*)$", r["key"])
        if not m:
            continue
        d = WEEKDAYS.index(m.group(1).strip()) if m.group(1).strip() in WEEKDAYS else -1
        if d < 0:
            continue
        label = m.group(2).strip()
        if not label:
            continue
        out[f"{d}|{label}"] = {
            "day": d,
            "weekday": WEEKDAYS[d],
            "label": label,
            "status": CN_TO_STATUS.get(r["status_cn"], ""),
            "status_cn": r["status_cn"],
            "note": r["note"],
        }
    return out


def set_review(text: str, day: int, label: str, status: str, note: str) -> str:
    target = f"{WEEKDAYS[day]} · {label}"
    rows = [r for r in review_rows_from(text) if r["key"] != target]
    status_cn = STATUS_TO_CN.get(status, "")
    if status_cn or note:
        rows.append({"key": target, "status_cn": status_cn, "note": note})

    def esc(v: str) -> str:
        return re.sub(r"(?<!\\)\|", r"\\|", str(v)).replace("\n", "<br>")

    table = "\n".join(
        ["| 位置 | 状态 | 批注 |", "| :--- | :---: | :--- |"]
        + [f"| {esc(r['key'])} | {esc(r['status_cn'])} | {esc(r['note'])} |" for r in rows]
    )

    start = text.find(REVIEW_START)
    end = text.find(REVIEW_END, start) if start != -1 else -1
    if start != -1 and end != -1:
        return text[:start] + REVIEW_START + "\n" + table + "\n" + REVIEW_END + text[end + len(REVIEW_END):]
    section = f"{REVIEW_HEADING}\n\n{REVIEW_START}\n{table}\n{REVIEW_END}"
    return re.sub(r"\s*$", "", text) + "\n\n" + section + "\n"


# ---------------------------------------------------------------- 文件定位
def folder_of(args) -> Path:
    vault = Path(args.vault).expanduser()
    if not vault.is_dir():
        raise SystemExit(f"✗ vault 目录不存在：{vault}")
    folder = vault / (args.folder or "日程规划")
    return folder


def iter_week_files(folder: Path):
    if not folder.is_dir():
        return
    for p in sorted(folder.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        fm, _ = parse_frontmatter(text)
        if fm.get("type") != "周计划":
            continue
        try:
            week = int(str(fm.get("week", "")).strip())
        except ValueError:
            continue
        yield p, text, fm, week


def find_week(folder: Path, week: int):
    for p, text, fm, w in iter_week_files(folder):
        if w == week:
            return p, text, fm
    raise SystemExit(f"✗ 没找到第 {week} 周（目录：{folder}）")


def backup(path: Path, keep: int = 40) -> Path:
    d = path.parent / ".weekly-plan-backups"
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dst = d / f"{path.stem}.{stamp}.bak"
    dst.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    olds = sorted(d.glob(f"{path.stem}.*.bak"))
    for f in olds[: max(0, len(olds) - keep)]:
        f.unlink(missing_ok=True)
    return dst


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- 模板
def build_week_text(week: int, start: str, end: str, title: str | None = None) -> str:
    t = title or f"第 {week} 周计划"
    table = "\n".join(
        build_table_line([f"**{r}**" if r else "", *[""] * 7]) for r in DEFAULT_ROWS
    )
    return f"""---
title: "{t}"
type: 周计划
week: {week}
start: {start}
end: {end}
cssclasses:
  - weekly-plan
tags:
  - 计划表
  - 周计划
---

> [!quote] 保持热爱，早睡早起。
> *Freedom is from within.*

> [!tip] 时段配色
> {LEGEND}

# {t}

**周期：** {start}（周一） → {end}（周日）

| 第 {week} 周计划 | 周一 | 周二 | 周三 | 周四 | 周五 | 周六 | 周日 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
{table}
"""


TEMPLATE_MD = """---
title: 周计划模板
type: 模板
cssclasses:
  - weekly-plan
tags:
  - 计划表
  - 周计划
  - 模板
---

> [!quote] 保持热爱，早睡早起。
> *Freedom is from within.*

> [!tip] 时段配色
> {legend}

# 第 {{week}} 周计划

**周期：** {{{{date:YYYY-MM-DD}}}} → 周日

{table}

## 使用说明

把本模板复制一份，改名为「第 N 周计划」，然后更新 frontmatter：

- `week`：周次（数字）
- `start` / `end`：周一 / 周日的日期
- `type` 必须保持 `周计划`，网页端和 Skill 靠它识别

单元格内换行用 `<br>`。
"""


INDEX_MD = """---
title: 日程规划
type: 索引
cssclasses:
  - weekly-plan
tags:
  - 计划表
  - 周计划
---

> [!quote] 保持热爱，早睡早起。
> *Freedom is from within.*

# 日程规划

这个文件夹存放每周计划。每周复制一次 [[周计划模板]]，按 `第 N 周计划` 命名。

## 说明

- 网页端和 Skill 都靠 frontmatter 的 `type: 周计划` 识别笔记。
- 复盘批注会自动写在每篇笔记末尾的「📝 复盘批注」区块里。
- 单元格换行用 `<br>`。
"""


def css_snippet() -> str:
    return """/* 私人日程管理助手 — 周计划笔记样式
   仅对带 weekly-plan 类的笔记生效。 */

.weekly-plan {
  --wp-accent: #496b8a;
  --wp-line: rgba(73, 107, 138, 0.25);
  --wp-morning: rgba(246, 216, 168, 0.28);
  --wp-class: rgba(207, 227, 245, 0.42);
  --wp-noon: rgba(255, 228, 199, 0.42);
  --wp-afternoon: rgba(221, 235, 215, 0.46);
  --wp-evening: rgba(231, 221, 247, 0.48);
  --wp-night: rgba(224, 231, 240, 0.52);
  --wp-review: rgba(248, 228, 236, 0.48);
  --wp-notes: rgba(243, 239, 230, 0.52);
}

/* 放宽内容宽度：Obsidian 默认「可读行宽」会挤窄表格 */
.weekly-plan,
.weekly-plan.markdown-preview-view,
.weekly-plan.markdown-source-view,
.weekly-plan .markdown-preview-view,
.weekly-plan .markdown-source-view {
  --file-line-width: 1600px;
}

.weekly-plan .markdown-preview-sizer,
.weekly-plan .markdown-preview-view .markdown-preview-sizer,
.weekly-plan.markdown-preview-view .markdown-preview-sizer,
.weekly-plan .cm-sizer,
.weekly-plan .markdown-source-view .cm-sizer,
.weekly-plan.markdown-source-view .cm-sizer {
  max-width: none !important;
  width: 100% !important;
}

.weekly-plan table {
  width: max-content;
  min-width: 100%;
  table-layout: fixed;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid var(--wp-line);
  border-radius: 16px;
}

.weekly-plan table th,
.weekly-plan table td {
  text-align: center;
  min-width: 112px;
  padding: 10px 12px;
  border-right: 1px solid var(--wp-line);
  border-bottom: 1px solid var(--wp-line);
  vertical-align: middle;
}

.weekly-plan table th:first-child,
.weekly-plan table td:first-child {
  width: 150px;
  min-width: 150px;
  font-weight: 700;
  color: var(--wp-accent);
  background: rgba(73, 107, 138, 0.1);
}

.weekly-plan table th {
  color: var(--wp-accent);
  font-weight: 750;
  background: linear-gradient(180deg, rgba(255,255,255,0.88), rgba(73,107,138,0.1));
}

.weekly-plan .wp-legend {
  display: inline-block;
  margin: 1px 5px 1px 0;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 0.84em;
  font-weight: 650;
}
.weekly-plan .wp-legend.morning { background: var(--wp-morning); }
.weekly-plan .wp-legend.class { background: var(--wp-class); }
.weekly-plan .wp-legend.noon { background: var(--wp-noon); }
.weekly-plan .wp-legend.afternoon { background: var(--wp-afternoon); }
.weekly-plan .wp-legend.evening { background: var(--wp-evening); }
.weekly-plan .wp-legend.night { background: var(--wp-night); }
.weekly-plan .wp-legend.review { background: var(--wp-review); }
.weekly-plan .wp-legend.notes { background: var(--wp-notes); }

/* 行分区配色 */
.weekly-plan table tbody tr:nth-child(-n+3) td:not(:first-child) { background-color: var(--wp-morning); }
.weekly-plan table tbody tr:nth-child(4) td:not(:first-child),
.weekly-plan table tbody tr:nth-child(5) td:not(:first-child) { background-color: var(--wp-class); }
.weekly-plan table tbody tr:nth-child(6) td:not(:first-child) { background-color: var(--wp-noon); }
.weekly-plan table tbody tr:nth-child(7) td:not(:first-child),
.weekly-plan table tbody tr:nth-child(8) td:not(:first-child) { background-color: var(--wp-afternoon); }
.weekly-plan table tbody tr:nth-child(9) td:not(:first-child) { background-color: var(--wp-evening); }
.weekly-plan table tbody tr:nth-child(n+10):nth-child(-n+15) td:not(:first-child) { background-color: var(--wp-night); }
.weekly-plan table tbody tr:nth-child(n+16):nth-child(-n+18) td:not(:first-child) { background-color: var(--wp-review); }
.weekly-plan table tbody tr:nth-child(n+19) td:not(:first-child) { background-color: var(--wp-notes); }

.weekly-plan table tr:last-child td { border-bottom: 0; }
.weekly-plan table th:last-child,
.weekly-plan table td:last-child { border-right: 0; }
"""


# ---------------------------------------------------------------- 子命令
def cmd_init_vault(a):
    vault = Path(a.vault).expanduser()
    vault.mkdir(parents=True, exist_ok=True)
    folder = vault / (a.folder or "日程规划")
    folder.mkdir(parents=True, exist_ok=True)

    created = []
    tmpl = folder / "周计划模板.md"
    if not tmpl.exists() or a.force:
        table = "\n".join(build_table_line([f"**{r}**" if r else "", *[""] * 7]) for r in DEFAULT_ROWS)
        tmpl.write_text(TEMPLATE_MD.format(legend=LEGEND, table=table), encoding="utf-8")
        created.append(str(tmpl))

    index = folder / "日程规划总览.md"
    if not index.exists() or a.force:
        index.write_text(INDEX_MD, encoding="utf-8")
        created.append(str(index))

    snip_dir = vault / ".obsidian" / "snippets"
    snip_dir.mkdir(parents=True, exist_ok=True)
    snip = snip_dir / "weekly-plan.css"
    if not snip.exists() or a.force:
        snip.write_text(css_snippet(), encoding="utf-8")
        created.append(str(snip))

    # 启用 CSS 片段
    appearance = vault / ".obsidian" / "appearance.json"
    data = {}
    if appearance.exists():
        try:
            data = json.loads(appearance.read_text(encoding="utf-8") or "{}")
        except Exception:
            data = {}
    enabled = data.get("enabledCssSnippets") or []
    if "weekly-plan" not in enabled:
        enabled.append("weekly-plan")
        data["enabledCssSnippets"] = enabled
        appearance.parent.mkdir(parents=True, exist_ok=True)
        appearance.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(str(appearance))

    print(f"✓ 初始化完成：{folder}")
    for c in created:
        print(f"  新建 {c}")
    if not created:
        print("  （已存在，未改动；加 --force 可覆盖）")


def cmd_new_week(a):
    folder = folder_of(a)
    folder.mkdir(parents=True, exist_ok=True)
    start = a.start
    end = a.end or (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
    title = a.title or f"第 {a.week} 周计划"
    path = folder / f"{title}.md"
    if path.exists() and not a.force:
        raise SystemExit(f"✗ 已存在：{path}（加 --force 覆盖）")
    path.write_text(build_week_text(a.week, start, end, title), encoding="utf-8")
    print(f"✓ 已创建 {path}")


def cmd_list_weeks(a):
    folder = folder_of(a)
    weeks = []
    for p, text, fm, w in iter_week_files(folder):
        pw = parse_week_text(text)
        rev = parse_reviews(text)
        weeks.append({
            "week": w,
            "file": str(p),
            "title": fm.get("title", ""),
            "start": fm.get("start", ""),
            "end": fm.get("end", ""),
            "rows": len(pw["rows"]) if pw else 0,
            "reviews": len(rev),
        })
    weeks.sort(key=lambda x: x["week"])
    if a.json:
        print(json.dumps(weeks, ensure_ascii=False, indent=2))
    else:
        if not weeks:
            print(f"（{folder} 里还没有周计划）")
        for w in weeks:
            print(f"第 {w['week']:>2} 周  {w['start'] or '未设周期':<12} 行 {w['rows']:>2}  复盘 {w['reviews']}  {Path(w['file']).name}")


def cmd_show_week(a):
    folder = folder_of(a)
    path, text, fm = find_week(folder, a.week)
    pw = parse_week_text(text)
    if not pw:
        raise SystemExit(f"✗ 没解析出表格：{path}")
    rev = parse_reviews(text)
    if a.json:
        print(json.dumps({
            "week": a.week, "file": str(path), "days": pw["days"],
            "rows": [{"label": r["label"], "values": r["values"]} for r in pw["rows"]],
            "reviews": rev,
        }, ensure_ascii=False, indent=2))
        return
    print(f"# 第 {a.week} 周  ({fm.get('start','')} → {fm.get('end','')})")
    print("      " + "".join(f"{d:<16}" for d in pw["days"]))
    for r in pw["rows"]:
        cells = []
        for i, v in enumerate(r["values"]):
            rv = rev.get(f"{i}|{r['label']}")
            mark = {"done": "✓", "partial": "~", "miss": "✕"}.get(rv["status"], "·") if rv else "·"
            cells.append(f"{mark}{v}".replace("<br>", " / ")[:15])
        print(f"{r['label']:<14}" + "".join(f"{c:<16}" for c in cells))
    if rev:
        print("\n## 复盘批注")
        for k, v in rev.items():
            print(f"  {v['weekday']} · {v['label']}  [{v['status_cn'] or '—'}]  {v['note']}")


def _resolve_row(pw, label):
    for r in pw["rows"]:
        if r["label"] == label:
            return r
    raise SystemExit(f"✗ 没找到行「{label}」\n  可用：{', '.join(x['label'] or '(空)' for x in pw['rows'])}")


def cmd_set_cell(a):
    folder = folder_of(a)
    path, text, _ = find_week(folder, a.week)
    pw = parse_week_text(text)
    if not pw:
        raise SystemExit(f"✗ 没解析出表格：{path}")
    row = _resolve_row(pw, a.row)
    d = day_index(a.day) if a.day else None
    if d is None:
        raise SystemExit("✗ 需要 --day（周一..周日 或 1..7）")
    lines = text.split("\n")
    cells = split_table_line(lines[row["line"]])
    while len(cells) < 8:
        cells.append("")
    cells[d + 1] = normalize_value(a.value)
    backup(path)
    lines[row["line"]] = build_table_line(cells)
    write_atomic(path, "\n".join(lines))
    print(f"✓ {WEEKDAYS[d]} · {a.row} = {a.value!r}")


def cmd_add_row(a):
    folder = folder_of(a)
    path, text, _ = find_week(folder, a.week)
    pw = parse_week_text(text)
    if not pw:
        raise SystemExit(f"✗ 没解析出表格：{path}")
    lines = text.split("\n")
    if a.after:
        pos = _resolve_row(pw, a.after)["line"]
    else:
        pos = pw["table_end"]
    new_line = build_table_line([f"**{strip_stars(a.label)}**", *[""] * 7])
    backup(path)
    lines.insert(pos + 1, new_line)
    write_atomic(path, "\n".join(lines))
    print(f"✓ 已在 {a.after or '(表格末尾)'} 之后插入行「{strip_stars(a.label)}」")


def cmd_delete_row(a):
    folder = folder_of(a)
    path, text, _ = find_week(folder, a.week)
    pw = parse_week_text(text)
    if not pw:
        raise SystemExit(f"✗ 没解析出表格：{path}")
    row = _resolve_row(pw, a.row)
    lines = text.split("\n")
    backup(path)
    del lines[row["line"]]
    write_atomic(path, "\n".join(lines))
    print(f"✓ 已删除行「{a.row}」")


def cmd_set_review(a):
    folder = folder_of(a)
    path, text, _ = find_week(folder, a.week)
    d = day_index(a.day)
    raw = (a.status or "").strip()
    if raw in ("", "清除", "clear", "none", "-"):
        status = ""
    elif raw in STATUS_TO_CN:          # 英文 token：done / partial / miss
        status = raw
    elif raw in CN_TO_STATUS:          # 中文：完成 / 部分 / 未完成
        status = CN_TO_STATUS[raw]
    else:
        raise SystemExit(f"✗ 状态只能是 完成 / 部分 / 未完成 / 清除，收到：{a.status}")
    # 允许只改批注、保留原状态
    pw = parse_week_text(text)
    if pw:
        _resolve_row(pw, a.row)
    existing = parse_reviews(text).get(f"{d}|{a.row}", {})
    if status == "" and a.note is None:
        pass
    elif status == "" and existing.get("status"):
        status = existing["status"]
    note = a.note if a.note is not None else existing.get("note", "")
    backup(path)
    write_atomic(path, set_review(text, d, a.row, status, note))
    print(f"✓ {WEEKDAYS[d]} · {a.row} → {STATUS_TO_CN.get(status,'(清除)')}"
          + (f"  「{note}」" if note else ""))


def cmd_list_reviews(a):
    folder = folder_of(a)
    path, text, _ = find_week(folder, a.week)
    rev = parse_reviews(text)
    if a.json:
        print(json.dumps(rev, ensure_ascii=False, indent=2))
        return
    if not rev:
        print("（这一周还没有复盘批注）")
        return
    order = sorted(rev.values(), key=lambda x: (x["day"], x["label"]))
    for r in order:
        print(f"{r['weekday']} · {r['label']:<18} [{r['status_cn'] or '—'}]  {r['note']}")


# ---------------------------------------------------------------- 入口
def main() -> None:
    ap = argparse.ArgumentParser(description="私人日程管理助手 — Obsidian 周计划读写")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--vault", required=True, help="Obsidian vault 根目录")
        p.add_argument("--folder", default="日程规划", help="存放周计划的子目录（默认：日程规划）")

    p = sub.add_parser("init-vault", help="初始化目录、模板与 CSS 片段")
    p.add_argument("--vault", required=True)
    p.add_argument("--folder", default="日程规划")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init_vault)

    p = sub.add_parser("new-week", help="新建一周")
    common(p); p.add_argument("--week", type=int, required=True)
    p.add_argument("--start", required=True, help="周一日期 YYYY-MM-DD")
    p.add_argument("--end", help="周日日期，省略则自动 +6 天")
    p.add_argument("--title"); p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_new_week)

    p = sub.add_parser("list-weeks", help="列出所有周")
    common(p); p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list_weeks)

    p = sub.add_parser("show-week", help="查看某一周")
    common(p); p.add_argument("--week", type=int, required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show_week)

    p = sub.add_parser("set-cell", help="写入某个单元格")
    common(p); p.add_argument("--week", type=int, required=True)
    p.add_argument("--row", required=True); p.add_argument("--day", required=True)
    p.add_argument("--value", default="")
    p.set_defaults(func=cmd_set_cell)

    p = sub.add_parser("add-row", help="新增一行时段")
    common(p); p.add_argument("--week", type=int, required=True)
    p.add_argument("--label", required=True); p.add_argument("--after")
    p.set_defaults(func=cmd_add_row)

    p = sub.add_parser("delete-row", help="删除一行时段")
    common(p); p.add_argument("--week", type=int, required=True)
    p.add_argument("--row", required=True)
    p.set_defaults(func=cmd_delete_row)

    p = sub.add_parser("set-review", help="写入复盘状态与批注")
    common(p); p.add_argument("--week", type=int, required=True)
    p.add_argument("--row", required=True); p.add_argument("--day", required=True)
    p.add_argument("--status", default="", help="完成 / 部分 / 未完成 / 清除")
    p.add_argument("--note", default=None, help="批注内容；不传则保留原有批注")
    p.set_defaults(func=cmd_set_review)

    p = sub.add_parser("list-reviews", help="列出某一周的复盘批注")
    common(p); p.add_argument("--week", type=int, required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list_reviews)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
