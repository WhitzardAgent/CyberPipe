#!/usr/bin/env python3
"""从 HuggingFace 拉取 mid-training 参考数据集的样本条目，存为 research/reference/samples/*.jsonl
可重复运行；每个数据集失败不影响其它。"""
import json, os, sys, traceback
# 兼容 shim：本机 scipy 过老，使用 numpy 1.24 已移除的 np.long/np.ulong，import datasets 前补齐
import numpy as np
if not hasattr(np, "long"):
    np.long = int
if not hasattr(np, "ulong"):
    np.ulong = np.uint
from datasets import load_dataset
from huggingface_hub import hf_hub_download, HfApi

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "samples")
CARDS = os.path.join(BASE, "cards")
os.makedirs(OUT, exist_ok=True)
os.makedirs(CARDS, exist_ok=True)

TRUNC = 80_000  # 单字段截断上限，防轨迹类超大样本撑爆文件

def trunc(v):
    if isinstance(v, str) and len(v) > TRUNC:
        return v[:TRUNC] + f"\n...[TRUNCATED, total {len(v)} chars]"
    if isinstance(v, list):
        return [trunc(x) for x in v]
    if isinstance(v, dict):
        return {k: trunc(x) for k, x in v.items()}
    return v

def dump(name, rows):
    p = os.path.join(OUT, f"{name}.jsonl")
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(trunc(r), ensure_ascii=False) + "\n")
    print(f"  saved {p} ({len(rows)} rows)")

def stream_take(repo, n, config=None, split="train", **kw):
    ds = load_dataset(repo, config, split=split, streaming=True, **kw)
    return [dict(r) for r in ds.take(n)]

def save_card(repo_id):
    try:
        p = hf_hub_download(repo_id, "README.md", repo_type="dataset")
        dst = os.path.join(CARDS, repo_id.replace("/", "__") + ".README.md")
        with open(p, "rb") as a, open(dst, "wb") as b:
            b.write(a.read())
        print(f"  card saved {dst}")
    except Exception as e:
        print(f"  card unavailable: {type(e).__name__}")

TASKS = [
    # (输出名, 拉取函数)
    ("fim-midtraining-400K", lambda: stream_take("TIGER-Lab/FIM-Midtraining-400K", 20)),
    ("agenttrove", lambda: stream_take("open-thoughts/AgentTrove", 12)),
    ("smoltalk2-mid-nemotron", lambda: stream_take("HuggingFaceTB/smoltalk2", 8, config="Mid", split="Llama_Nemotron_Post_Training_Dataset_reasoning_r1")),
    ("smoltalk2-mid-openthoughts3", lambda: stream_take("HuggingFaceTB/smoltalk2", 8, config="Mid", split="OpenThoughts3_1.2M")),
    ("megamath-web-pro-max", lambda: stream_take("OctoThinker/MegaMath-Web-Pro-Max", 15)),
    ("nemotron-specialized-code-concepts", lambda: stream_take("nvidia/Nemotron-Pretraining-Specialized-v1.1", 15, config="Nemotron-Pretraining-Code-Concepts")),
    ("octolong-cross-repo", lambda: stream_take("OctoLong/cross-repo-code-sample", 10)),
    # gated：尝试匿名拉取，预期失败但记录
    ("midtool-mix", lambda: stream_take("MidTool/MidTool-Mix", 8, config="web")),
    ("davinci-dev", lambda: stream_take("GAIR/daVinci-Dev", 8)),
    ("primus-seed", lambda: stream_take("trendmicro-ailab/Primus-Seed", 8)),    # 安全域 instruction/pentest 类（SFT 风格，作为内容形态参考）
    ("pentest-agent-chatml", lambda: stream_take("7h3-R3v3n4n7/pentest-agent-dataset-chatml", 10)),
    ("bug-bounty-pentest-en", lambda: stream_take("AYI-NEDJIMI/bug-bounty-pentest-en", 10)),
    ("win-exe-malware-analysis", lambda: stream_take("Thcrull/win-exe-malware-analysis", 10)),
    ("trendyol-cybersec-instruct", lambda: stream_take("Trendyol/Trendyol-Cybersecurity-Instruction-Tuning-Dataset", 10)),
]

OPEN_CARDS = [
    "TIGER-Lab/FIM-Midtraining-400K", "open-thoughts/AgentTrove", "HuggingFaceTB/smoltalk2",
    "OctoThinker/MegaMath-Web-Pro-Max", "nvidia/Nemotron-Pretraining-Specialized-v1.1",
    "OctoLong/cross-repo-code-sample", "7h3-R3v3n4n7/pentest-agent-dataset-chatml",
    "AYI-NEDJIMI/bug-bounty-pentest-en", "Thcrull/win-exe-malware-analysis",
    "Trendyol/Trendyol-Cybersecurity-Instruction-Tuning-Dataset",
    "MidTool/MidTool-Mix", "GAIR/daVinci-Dev", "trendmicro-ailab/Primus-Seed",
]

def fetch_dolmino():
    """dolmino 是 14 万个 jsonl.zst 文件，探目录后挑与网页/论坛最接近的小分片。"""
    api = HfApi()
    files = api.list_repo_files("allenai/dolma3_dolmino_mix-100B-1125", repo_type="dataset")
    dirs = sorted({"/".join(f.split("/")[:2]) for f in files if f.count("/") >= 2})
    print(f"  dolmino top dirs: {dirs}")
    pref = [f for f in files if "stackexchange" in f.lower()] or \
           [f for f in files if "wiki" in f.lower()] or \
           [f for f in files if "/web" in f.lower() and f.endswith(".jsonl.zst")] or \
           [f for f in files if f.endswith(".jsonl.zst")]

def fetch_dolmino_subset(files, pattern, n=8, prefer_smallest=True):
    """从 dolmino 文件列表中按 pattern 选分片并读前 n 行。"""
    api = HfApi()
    cand = [f for f in files if pattern in f and f.endswith(".jsonl.zst")]
    if not cand:
        return None, None
    best, best_sz = None, None
    for f in cand[:5]:
        try:
            info = api.get_paths_info("allenai/dolma3_dolmino_mix-100B-1125", [f], repo_type="dataset")
            for p in info:
                if getattr(p, "size", 0) and (best_sz is None or p.size < best_sz):
                    best, best_sz = f, p.size
        except Exception:
            continue
    print(f"  chosen: {best} ({(best_sz or 0)/1e6:.2f} MB)")
    local = hf_hub_download("allenai/dolma3_dolmino_mix-100B-1125", best, repo_type="dataset")
    try:
        import zstandard
    except ImportError:
        os.system(f"{sys.executable} -m pip install -q zstandard")
        import zstandard
    import io
    dctx = zstandard.ZstdDecompressor()
    rows = []
    with open(local, "rb") as fh:
        text = io.TextIOWrapper(dctx.stream_reader(fh), encoding="utf-8", errors="replace")
        for line in text:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if len(rows) >= n:
                break
    return best, rows

def fetch_dolmino_multi():
    """拉取 dolmino 中对安全管线最有参考价值的三个子集：StackEdu-FIM、CC 高质网页(software)、olmOCR PDF。"""
    api = HfApi()
    files = api.list_repo_files("allenai/dolma3_dolmino_mix-100B-1125", repo_type="dataset")
    out = {}
    for tag, pattern in [
        ("stackedu-fim-shell", "stack_edu-fim_vigintile_15_Shell"),
        ("stackedu-fim-python", "stack_edu-fim_vigintile_15_Python"),
        ("cc-hq-software-dev", "high-quality_19_software_development"),
        ("olmocr-pdf-software", "olmocr_science_pdfs-high_quality-software_dev-2e12"),
    ]:
        name, rows = fetch_dolmino_subset(files, pattern)
        if rows:
            out[tag] = {"file": name, "rows": rows}
    return out

def fetch_midtool_classifiers():
    """MidTool 的两个 fastText 质量分类器（Apache-2.0），作为质量过滤参考资产。"""
    api = HfApi()
    models = [m.id for m in api.list_models(author="MidTool")]
    print(f"  MidTool models: {models}")
    got = []
    for m in models:
        if "fasttext" in m.lower():
            for fn in api.list_repo_files(m):
                if fn.endswith((".bin", ".vec")) or "README" in fn:
                    try:
                        p = hf_hub_download(m, fn)
                        got.append(p)
                        print(f"  downloaded {m}/{fn} -> {p}")
                    except Exception as e:
                        print(f"  {m}/{fn}: {type(e).__name__}")
    return got

def main():
    print("=== 样本拉取 ===")
    for name, fn in TASKS:
        print(f"\n--- {name} ---")
        try:
            rows = fn()
            dump(name, rows)
            if rows:
                print(f"  fields: {list(rows[0].keys())}")
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {str(e)[:200]}")

    print("\n--- dolmino 多分片 ---")
    try:
        bundles = fetch_dolmino_multi()
        for tag, bundle in bundles.items():
            print(f"  [{tag}] {bundle['file']}")
            dump(f"dolmino-{tag}", bundle["rows"])
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {str(e)[:200]}")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {str(e)[:200]}")

    print("\n=== 数据卡抓取 ===")
    for cid in OPEN_CARDS:
        print(f"\n--- {cid} ---")
        save_card(cid)

    print("\n=== MidTool fastText 分类器资产 ===")
    try:
        fetch_midtool_classifiers()
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {str(e)[:200]}")

if __name__ == "__main__":
    main()
