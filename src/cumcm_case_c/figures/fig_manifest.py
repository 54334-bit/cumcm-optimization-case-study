# -*- coding: utf-8 -*-
r"""图件清单（manifest）与交付质检。

每张图必须配一条 manifest：filename / purpose / data_source / key_values。
评审与复核都用它对齐「图内数字 ↔ checkpoint」，也是手册 §8.2 的硬要求。

用法
-----
    from fig_manifest import Manifest
    m = Manifest(root=r"D:\CMUCU\6对话\output\figures", group="q2")
    m.add(name="q2_01_day_plan_exec",
          purpose="Q2 计划—执行日内全链（主口径：非预见 + 因果裕度）",
          data_source=["5对话/output/q2_emg_detail.json", "5对话/result2.xlsx"],
          key_values={"J_plan": 12891818.24, "J_emg": 360522.85},
          script="q2_fig_A_main.py")
    m.write()           # 落盘 <root>/q2/q2_figures_manifest.json（按 name 合并）
    print(m.check())    # 检查 svg+png 是否齐全

改动记录
--------
2026-09-11 22:0x 之前的版本 `write()` 是**整体覆盖**；本文件已改为**按 name 合并写入**
（与 `D:\CMUCU\4对话\code\fig_manifest.py` 的合并版对齐）。Q1 线当晚实测：eda 组由 3 个脚本
共写一份 manifest，`fig_eda_p2.py` 覆盖写入后把 `fig_eda_p1.py` 刚写的 4 条元数据冲成空白
（purpose/script 丢失、data_source 退化成通用串）。Q2 有 14 张图、必然多脚本，必须合并写。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class Manifest:
    # 各线共用的默认值（Q2 口径）。Q3/Q4 等其它线请显式传 key_values_source，
    # 避免清单里写着别条线的数据入口（2026-09-13 审计 R10 发现 2）。
    DEFAULT_KEY_VALUES_SOURCE = (
        "q2_data_causal.py（Q2 主口径唯一数据入口：q2_emg_detail.json + result2.xlsx，"
        "先验 sha256 再对锚点；图内数值由脚本现算）")

    def __init__(self, root: str, group: str, key_values_source: str | None = None):
        self.root = Path(root)
        self.group = group
        self.key_values_source = key_values_source or self.DEFAULT_KEY_VALUES_SOURCE
        self.dir = self.root / group
        self.dir.mkdir(parents=True, exist_ok=True)
        self.items: list[dict] = []

    def add(self, *, name: str, purpose: str, data_source, key_values: dict,
            script: str, note: str = "") -> None:
        self.items.append({
            "name": name,
            "purpose": purpose,
            "data_source": data_source if isinstance(data_source, list) else [data_source],
            "key_values": key_values,
            "script": script,
            "note": note,
            "files": {"png": f"{name}.png", "svg": f"{name}.svg"},
        })

    def check(self) -> list[str]:
        """返回缺失文件列表（空=齐全）。"""
        missing = []
        for it in self.items:
            for fmt, fn in it["files"].items():
                if not (self.dir / fn).exists():
                    missing.append(f"{it['name']}.{fmt}")
        return missing

    def write(self) -> Path:
        """**按 name 合并**写入本组 manifest（禁止整体覆盖）。

        同名条目用本次写入的内容，其余原样保留，新条目追加到末尾。
        这样无论多少脚本、以什么顺序写同一份清单，都不会互相冲掉元数据。
        """
        out = self.dir / f"{self.group}_figures_manifest.json"

        prev_figs: list[dict] = []
        if out.exists():
            try:
                prev_figs = json.loads(out.read_text(encoding="utf-8")).get("figures", []) or []
            except Exception:
                prev_figs = []

        by_name = {it["name"]: it for it in self.items}
        merged: list[dict] = []
        for it in prev_figs:
            nm = it.get("name")
            if nm in by_name:
                merged.append(by_name.pop(nm))
            else:
                merged.append(it)
        merged.extend(by_name.values())

        payload = {
            "group": self.group,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "figure_dir": str(self.dir),
            "dpi": 300,
            "formats": ["svg", "png"],
            "count": len(merged),
            "key_values_source": self.key_values_source,
            "figures": merged,
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out
