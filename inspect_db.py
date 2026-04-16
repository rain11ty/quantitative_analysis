# -*- coding: utf-8 -*-
import os, sys, re, json, inspect

from pathlib import Path

sys.path.insert(0, "d:/G/工作与学习/大四下/lianghua/quantitative_analysis")
from app import create_app
from app.extensions import db

app = create_app('default')
ctx = app.app_context()
ctx.push()

from app import models as app_models

model_classes = []
for name, obj in inspect.getmembers(app_models):
    if inspect.isclass(obj) and hasattr(obj, '__tablename__') and issubclass(obj, db.Model):
        model_classes.append(obj)

app_dir = Path("d:/G/工作与学习/大四下/lianghua/quantitative_analysis/app")
init_dir = Path("d:/G/工作与学习/大四下/lianghua/quantitative_analysis/init")

used_classes = set()
for d in [app_dir, init_dir]:
    for f in d.rglob("*.py"):
        if "models" in f.parts: 
            continue
        try:
            content = f.read_text(encoding="utf-8")
            for cls in model_classes:
                if re.search(r"\b" + cls.__name__ + r"\b", content):
                    used_classes.add(cls)
                # also check if table name is used in raw sql
                elif re.search(r"\b" + cls.__tablename__ + r"\b", content):
                    used_classes.add(cls)
        except Exception:
            pass

result = {"used": [], "unused": []}
for cls in model_classes:
    table_name = cls.__tablename__
    cols = []
    for col in cls.__table__.columns:
        cols.append({
            "name": col.name,
            "type": str(col.type),
            "pk": "是" if col.primary_key else "否",
            "comment": col.comment or ""
        })
    item = {
        "class_name": cls.__name__,
        "table_name": table_name,
        "columns": cols,
        "doc": cls.__doc__ or ""
    }
    if cls in used_classes:
        result["used"].append(item)
    else:
        result["unused"].append(item)

Path("d:/G/工作与学习/大四下/lianghua/db_schema_dump.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Dumped {len(model_classes)} models. Used: {len(result['used'])}, Unused: {len(result['unused'])}")
