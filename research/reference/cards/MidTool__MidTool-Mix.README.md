---
license: other
license_name: midtool-mix-license
license_link: LICENSE
task_categories:
- text-generation
language:
- en
tags:
- agentic
- tool-use
- mid-training
- function-calling
- pretraining
size_categories:
- 10M<n<100M
configs:
- config_name: web
  data_files: web/*.parquet
- config_name: pdf
  data_files: pdf/*.parquet
- config_name: code
  data_files: code/*.parquet
- config_name: native-agent-traj
  data_files: native-agent-traj/*.parquet
extra_gated_heading: Access MidTool-Mix
extra_gated_prompt: >-
  By requesting access you agree to the MidTool-Mix License (see LICENSE in this
  repository), and you accept responsibility for complying with the upstream terms that
  apply to the portions you use. This corpus is assembled from public sources and was not
  manually reviewed. It is provided as is, without warranty of any kind. The authors accept
  no liability for its contents or for any use made of it.
extra_gated_button_content: Agree and access
---

# MidTool-Mix

A 20.3B-token mid-training corpus for **agentic tool use**. It pairs filtered web, PDF, and code sources with synthesized agent supervision, and is designed to teach models to recognize tool affordances, ground arguments from context, compose tool-call workflows, and recover from incomplete information — before any post-training.

Mid-training `Qwen3-4B-Base` / `Qwen3-8B-Base` on MidTool-Mix improves downstream tool use under both SFT and RL on BFCLv3, τ²-Bench, and MCP-Universe. See the [model collection](https://huggingface.co/collections/MidTool/midtool-release-6a72341cd74cc247adc57c80).

## Composition

| Subset | Tokens (B) | Samples | Ratio | Content |
|---|---|---|---|---|
| `web` | 4.4 / 4.1 | 6.86M | 42% | FineWeb technical pages (2020–2025), filtered |
| `pdf` | 2.6 / 2.1 | 1.34M | 23% | FinePDFs English subset, filtered |
| `code` | 3.8 / 1.5 | 2.60M | 26% | GitHub repos with documentation-like paths |
| `native-agent-traj` | 1.8 | 0.42M | 9% | Trajectories synthesized from real APIs and MCP skills |
| **Total** | **20.3** | **11.22M** | 100% | |

Slash-separated token counts are *source corpus / context-grounded augmentation*. Every sample is plain text under `text`; trajectories are normalized into a chat-style template with no special control tokens.

## Loading

```python
from datasets import load_dataset

ds = load_dataset("MidTool/MidTool-Mix", "code", split="train")
```

## Fields

All subsets carry `text`. Additionally:

- `web` — `id`, `url`, `dump`, `date`, `file_path`, `language`, `language_score`
- `pdf` — `id`, `url`, `language`, `language_score`, `ocr_quality_scores`
- `code` — `owner`, `repo`, `relpath`, `extension`, `size_bytes`, `sha256`, `commit_sha`
- `native-agent-traj` — `extra`, `src`

Web and PDF are filtered with our fastText quality classifiers, released alongside this dataset: [web](https://huggingface.co/MidTool/MidTool-fasttext-web-quality-classifier), [pdf](https://huggingface.co/MidTool/MidTool-fasttext-pdf-quality-classifier).

`native-agent-traj` mixes four components, identified by the `src` column: `nemetron-agentic` (335,122), `api-traj` (48,975), `awm-rollout` (23,135), `skill-traj` (17,540).

## Decontamination

Known benchmark and evaluation repositories are excluded by blacklist during code collection. The finished mixture was additionally audited with DeCon against BFCLv3, τ²-Bench, and MCP-Universe: fewer than 20 candidates were flagged, all from the web slice, and manual inspection found all of them to be false positives (shared surface *n*-grams in generic API documentation, no benchmark instances or reference answers). DeCon bounds verbatim overlap only; semantic or schema-level similarity is not covered.

## Limitations

- English only.
- Source documents are public web/PDF/GitHub content and are **not** manually reviewed. They may contain errors, outdated APIs, offensive material, or credentials committed by their original authors. Secret patterns detected in the `code` subset have been replaced with the sentinel `<SECRET>`; this scan is not exhaustive and other subsets were not modified.
- The `code` subset does not carry a per-file license column. Use `owner`/`repo`/`commit_sha` to resolve a file's license upstream if your use requires it.
- A large fraction of the corpus is model-generated. Trajectories pass automatic validation but were not human-verified.
- Improvements concentrate on general tool use. Deep-search-style exploratory behavior does not benefit measurably.

## Details

See our paper for the full data, training, and evaluation details.

```bibtex
@article{jiang2026midtool,
  title  = {MidTool: Mid-training Data Synthesis for Agentic Tool Use},
  author = {Jiang, Fengqing and Wang, Yite and Liu, Boyi and Wang, Zhaoyang and
            Xu, Canwen and Yao, Zhewei and Poovendran, Radha and He, Yuxiong},
  year   = {2026}
}
```
