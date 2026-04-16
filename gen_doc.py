# -*- coding: utf-8 -*-
import json

data = json.loads(open(r"d:/G/工作与学习/大四下/lianghua/db_schema_dump.json", encoding="utf-8").read())

md = ["# 数据库表结构说明\n\n本文档列出了系统当前实际使用的所有数据库表结构。\n\n## 1. 已使用的表\n"]

for t in data["used"]:
    md.append(f"### 表名：`{t['table_name']}`")
    md.append(f"**关联代码类**：`{t['class_name']}`")
    desc = t['doc'].strip() if t['doc'] else f"系统 {t['class_name']} 业务相关表。"
    md.append(f"**说明**：{desc}\n")
    md.append("| 字段名 | 字段类型 | 是否主键 | 描述/注释 |")
    md.append("|---|---|---|---|")
    for c in t["columns"]:
        md.append(f"| {c['name']} | {c['type']} | {c['pk']} | {c['comment']} |")
    md.append("\n")

md.append("## 2. 未使用的表\n\n以下模型表在系统中存在定义，但在核心业务代码中**未被实际引用**（可能是废弃、草稿或尚未使用）：\n")
for t in data["unused"]:
    md.append(f"- `{t['table_name']}` (对应类: `{t['class_name']}`)")

with open(r"d:/G/工作与学习/大四下/lianghua/数据库表结构.md", "w", encoding="utf-8") as f:
    f.write("\n".join(md))

print("生成成功！文件路径: d:/G/工作与学习/大四下/lianghua/数据库表结构.md")
