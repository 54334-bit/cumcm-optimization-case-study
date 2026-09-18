# -*- coding: utf-8 -*-
"""施工现场保护：给所有"只读外部依赖"打指纹（只读外部，只写 8对话\output）
用途：① 交付前证明我没碰别人的东西；② 若发生越界写入，能在下一次运行立刻检出。
用法：python site_guard_fingerprint.py            # 首次=生成指纹
      python site_guard_fingerprint.py --check    # 之后=比对，报出被改动/删除的文件
"""
import os, sys, json, hashlib, time

SELF = r"D:\CMUCU\8对话\output\site_guard_fingerprint.json"
WATCH_DIRS = [
    r"D:\CMUCU\7.6对话\output\v2b_full",
    r"D:\CMUCU\7.5对话\code",
    r"D:\CMUCU\Q3交付",
    r"D:\CMUCU\赛题\C题\附件\附件5",
    r"D:\CMUCU\B对话\clean",
    r"D:\CMUCU\5对话\code",
]
WATCH_FILES = [
    r"D:\CMUCU\7.5对话\code\q3_exec_v2b.py",
    r"D:\CMUCU\7.6对话\code\q76_v2b_full.py",
    r"D:\CMUCU\7.6对话\code\q76_materialize.py",
    r"D:\CMUCU\5对话\code\q2_milp_plan.py",
    r"D:\CMUCU\5对话\code\q2_v2_micro.py",
]
BIG = 512 * 1024          # >512KB 只记 size+mtime（避免每次读大文件）


def h(p):
    x = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            x.update(b)
    return x.hexdigest()


def snap():
    out = {}
    files = list(WATCH_FILES)
    for d in WATCH_DIRS:
        if os.path.isdir(d):
            for dp, dn, fn in os.walk(d):
                dn[:] = [x for x in dn if x not in ("__pycache__", ".git")]
                for f in fn:
                    files.append(os.path.join(dp, f))
    for p in files:
        if not os.path.isfile(p):
            continue
        st = os.stat(p)
        rec = {"size": st.st_size, "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))}
        if st.st_size <= BIG:
            rec["sha256"] = h(p)
        out[p] = rec
    return out


if __name__ == "__main__":
    cur = snap()
    if "--check" in sys.argv and os.path.exists(SELF):
        old = json.load(open(SELF, encoding="utf-8"))
        changed, gone, new = [], [], []
        for p, r in old.items():
            if p not in cur:
                gone.append(p)
            elif cur[p] != r:
                changed.append({"path": p, "old": r, "new": cur[p]})
        for p in cur:
            if p not in old:
                new.append(p)
        print("被改动 %d ｜ 被删除 %d ｜ 新增 %d" % (len(changed), len(gone), len(new)), flush=True)
        for c in changed:
            print("  ⚠ 改动: %s" % c["path"], flush=True)
            if "sha256" in c["old"] and "sha256" in c["new"] and c["old"]["sha256"] != c["new"]["sha256"]:
                print("      sha %s -> %s" % (c["old"]["sha256"][:12], c["new"]["sha256"][:12]), flush=True)
        for p in gone:
            print("  ⚠ 删除: %s" % p, flush=True)
        for p in new:
            print("  · 新增: %s" % p, flush=True)
    else:
        json.dump(cur, open(SELF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("已生成指纹：%d 个文件 -> %s" % (len(cur), SELF), flush=True)
