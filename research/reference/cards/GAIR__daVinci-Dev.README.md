---
pretty_name: daVinci-Dev (Agent-native Trajectories)
language:
- en
size_categories:
- 1M<n<10M
license: other
license_name: mixed-permissive-and-cc-by-4.0
license_link: https://creativecommons.org/licenses/by/4.0/
tags:
- software-engineering
- agent
- pull-request
- code
- synthetic
- trajectory
- patch
- github
- python
extra_gated_prompt: "By requesting access, you agree to the terms of the license and to cite the dataset in any resulting publications."
extra_gated_heading: "Please provide your full legal name and organization details. Avoid using acronyms where possible. Failure to provide accurate information may result in access denial."
extra_gated_button_content: "Submit Request"
extra_gated_fields:
  First Name: text
  Last Name: text
  Organization: text
  Country: country
  Job Title:
    type: select
    options:
      - Student
      - Researcher
      - AI Developer/Engineer
      - Data Scientist
      - Reporter
      - Other
  Intended Use:
    type: select
    options:
      - Research
      - Commercial
      - Education
      - Other
  geo: ip_location
  I agree to cite this dataset: checkbox
  I accept the license terms: checkbox
configs:
  - config_name: filtered_repos
    data_files:
    - split: train
      path: ctx-native/filtered_repos/*.parquet
  - config_name: filtered_prs
    data_files:
    - split: train
      path: ctx-native/filtered_prs/*.parquet
  - config_name: llm_enhanced_prs
    data_files:
    - split: train
      path: ctx-native/llm_enhanced_prs/*.parquet
  - config_name: env_native
    data_files:
    - split: train
      path: env-native.jsonl
---

<div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 10px">
  <img src="assets/sii.png" alt="SII" width="100px">
  <img src="assets/GAIR_Logo2.png" alt="GAIR" width="100px">
</div>

<div align="center">

[![Paper](https://img.shields.io/badge/Paper-PDF-1f6feb.svg)](https://github.com/GAIR-NLP/daVinci-Dev/blob/main/daVinci-Dev.pdf)
[![arXiv](https://img.shields.io/badge/arXiv-2601.18418-b31b1b.svg)](https://arxiv.org/pdf/2601.18418)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-green)](https://github.com/GAIR-NLP/daVinci-Dev)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Dataset-blue)](https://huggingface.co/datasets/GAIR/daVinci-Dev)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model-blue)](https://huggingface.co/GAIR/daVinci-Dev-72B)

</div>

<h1 align="center">daVinci-Dev Dataset: Agent-native Mid-training for Software Engineering</h1>

<div align="center">
  <img src="assets/teaser.png" width="100%" />
</div>

This dataset release contains **agent-native trajectories** used in *daVinci-Dev: Agent-native Mid-training for Software Engineering*.

## Table of Contents

- [Dataset at a glance](#dataset-at-a-glance)
- [Dataset files](#dataset-files)
- [Model Zoo](#model-zoo)
- [Pipeline](#pipeline)
- [Converting PR structure into LLM-trainable text](#converting-pr-structure-into-llm-trainable-text)
- [LLM enhancement details](#llm-enhancement-details)
- [Intended uses](#intended-uses)
- [License](#license)
- [Citation](#citation)

## Dataset at a glance

It includes two complementary data sources:

1. **Contextually-native trajectories \\(\mathcal{D}^{\text{ctx}}_{\text{py}}\\) (PR-derived, Python Variant)**
   - Constructed from GitHub pull requests.
   - We only include PRs from repositories with a **permissive license** in the open source release.
   - This is ~**60%** of the full PR-derived corpus, totaling ~**4.1M PRs**.
   - PR content is additionally summarized / enhanced with an LLM (details below).
   - The data is stored in structured parquet format. To convert it into LLM-trainable text, see the instructions below.

2. **Environmentally-native trajectories \\(\mathcal{D}^{\text{env}}_{\text{pass}}\\) (executable rollouts, test-passing subset)**
   - Collected by rolling out [**SWE-Agent**](https://github.com/SWE-agent/SWE-agent) with [**GLM-4.6**](https://huggingface.co/zai-org/GLM-4.6) in real repositories from the [**SWE-rebench**](https://huggingface.co/datasets/nebius/SWE-rebench) dataset.
   - The source dataset is **CC-BY-4.0**: https://huggingface.co/datasets/nebius/SWE-rebench

## Dataset files

### Contextually-native \\(\mathcal{D}^{\text{ctx}}_{\text{py}}\\) (PR-derived)

These parquet shards store a structured representation of PRs.

- Repository metadata (including detected license):
  - `./ctx-native/filtered_repos/part-0000.parquet`

contains one row per filtered repository with fields like `repo_id`, `full_name`, `description`, `language`, stars, and `license_key` (schema: [`models.PublicRepo`](https://github.com/GAIR-NLP/daVinci-Dev/blob/main/pipeline/models/models.go#L4)).

- PR metadata (small file containing basic info about each PR):
  - `./ctx-native/filtered_prs/part-0000.parquet`
  - `./ctx-native/filtered_prs/part-0001.parquet`
  - …

contain one row per PR with identifiers plus title/body/author metadata and coarse file-change stats (schema: [`models.PRMetadata`](https://github.com/GAIR-NLP/daVinci-Dev/blob/main/pipeline/models/models.go#L23)).

- Structured PR trajectories (LLM-enhanced):
  - `./ctx-native/llm_enhanced_prs/part-0000.parquet`
  - `./ctx-native/llm_enhanced_prs/part-0001.parquet`
  - `./ctx-native/llm_enhanced_prs/part-0002.parquet`
  - …

contain one row per PR with repo/PR text fields, related issue content, relevant file snapshots, commit diffs with refined commit messages, and an LLM-written PR summary (schema: [`models.LLMEnhancedPRData`](https://github.com/GAIR-NLP/daVinci-Dev/blob/main/pipeline/models/models.go#L148)).

### Environmentally-native \\(\mathcal{D}^{\text{env}}_{\text{pass}}\\) (executable rollouts)

- Test-passing subset in JSONL ([SWE-Agent](https://github.com/SWE-agent/SWE-agent) + [GLM-4.6](https://huggingface.co/zai-org/GLM-4.6) rollouts on [SWE-rebench](https://huggingface.co/datasets/nebius/SWE-rebench)):
  - `./env-native.jsonl`

## Model Zoo

Trained checkpoints are released on Hugging Face:

| Model | Description | Link |
|------|-------------|------|
| `daVinci-Dev-72B` | Final model (agent-native mid-training + env native SFT) | https://huggingface.co/GAIR/daVinci-Dev-72B |
| `daVinci-Dev-32B` | Final model (agent-native mid-training + env native SFT) | https://huggingface.co/GAIR/daVinci-Dev-32B |
| `daVinci-Dev-72B-MT` | **MT checkpoint** (after agent-native mid-training, **before SFT**) | https://huggingface.co/GAIR/daVinci-Dev-72B-MT |
| `daVinci-Dev-32B-MT` | **MT checkpoint** (after agent-native mid-training, **before SFT**) | https://huggingface.co/GAIR/daVinci-Dev-32B-MT |

## Pipeline

The GitHub repository contains a high-performance pipeline that calls the GitHub API and constructs the structured PR representation used to build $\mathcal{D}^{\text{ctx}}_{\text{py}}$.

| Pipeline | Description | Link |
|----------|---------|-------------|
| daVinci-Dev Pipeline | a high-performance pipeline used to build \\(\mathcal{D}^{\text{ctx}}_{\text{py}}\\) | [`GAIR-NLP/daVinci-Dev`](https://github.com/GAIR-NLP/daVinci-Dev) |

## Converting Datasets into LLM-trainable text

### Converting PR structure \\(\mathcal{D}^{\text{ctx}}_{\text{py}}\\)

To convert the structured PR representation into a linearized, LLM-trainable format, follow:

- https://github.com/GAIR-NLP/daVinci-Dev/blob/main/pipeline/text_from_huggingface.md

### Converting executable rollouts \\(\mathcal{D}^{\text{env}}_{\text{pass}}\\)

- https://github.com/GAIR-NLP/daVinci-Dev/blob/main/env_traj_utils/README.md

## LLM enhancement details

We used **Qwen/Qwen3-235B-A22B-Instruct-2507** (https://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct-2507) to:

- summarize PR content (e.g., description and commits), and
- enhance commit messages into more explicit, training-friendly descriptions.

## Intended uses

- Agentic software engineering mid-training (e.g., learning iterative edit patterns from PR histories).
- Research on PR understanding, patch generation, and edit planning.
- Building instruction-style corpora from structured PR data via the provided pipeline.

## License

This project is a **mixed** release:

- **Contextually-native PR-derived subset:** only PRs from repositories detected as having a **permissive license** are included. Each repo’s license is provided in `./ctx-native/filtered_repos/part-0000.parquet`.
- **Environmentally-native subset:** derived from [**SWE-rebench**](https://huggingface.co/datasets/nebius/SWE-rebench), licensed under **CC-BY-4.0**.
- **daVinci-Dev models:** released under [Qwen](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct/blob/main/LICENSE) license. Users should verify the licensing status of any generated code before using it in production.
- **daVinci-Dev pipeline:** released under the [Apache-2.0](https://github.com/GAIR-NLP/daVinci-Dev/blob/main/LICENSE) license.

Users are responsible for ensuring their downstream usage complies with the licenses of the underlying sources.

## Citation

If you use this work, please cite the daVinci-Dev paper.

```
@misc{zeng2026davincidevagentnativemidtrainingsoftware,
      title={daVinci-Dev: Agent-native Mid-training for Software Engineering},
      author={Ji Zeng and Dayuan Fu and Tiantian Mi and Yumin Zhuang and Yaxing Huang and Xuefeng Li and Lyumanshan Ye and Muhang Xie and Qishuo Hua and Zhen Huang and Mohan Jiang and Hanning Wang and Jifan Lin and Yang Xiao and Jie Sun and Yunze Wu and Pengfei Liu},
      year={2026},
      eprint={2601.18418},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2601.18418},
}
```
