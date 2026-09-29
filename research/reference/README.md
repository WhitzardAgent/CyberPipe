# Mid-training 参考数据标杆库

> **与 PLAN.md 附录 B 同源**（样本清单、关键观察、共性纪律、输出 schema 建议均已并入 PLAN.md 附录 B，远端开发可直接查阅主文档）。本 README 保留完整版本并承担本目录的操作说明职责。

**用途**：把我们管线要产出的每种数据类型，对照到 HF 上已验证的公开数据集的真实条目上——它们的 **schema 设计、metadata 纪律、文本形态**就是我方输出的对照标准。样本为真实条目（长字段截断至 80K 字符），`fetch_samples.py` 可随时重跑或扩量（登录 HF 并接受条款后可补齐 gated 三个）。

**目录**：
- `samples/*.jsonl` — 每个数据集 8–20 条真实样本
- `cards/*.README.md` — 13 个数据集的官方数据卡（含 gated 的 MidTool-Mix / daVinci-Dev / Primus-Seed）
- `fetch_samples.py` — 抓取脚本（可重跑；已内置本机 numpy/scipy 兼容 shim）

---

## 一、样本清单与我们场景的对应关系

我方爬取数据四类：**①漏洞分析/逆向 writeup、②渗透测试报告、③CTF writeup、④安全工具使用教程**。对应关系：

| 参考数据集 | 状态 | 参考价值 | 样本文件 |
|---|---|---|---|
| **Dolmino / dolma3**（OLMo 2/3 的 MT 数据） | 开放 | **最接近我方①③④的网页文本化形态**：CC 高质网页、olmOCR 文本化 PDF、StackEdu-FIM、wiki RCQA——看"清洗后文档长什么样、metadata 存什么" | `dolmino-cc-hq-software-dev / olmocr-pdf-software / stackedu-fim-{shell,python} / wiki-rcqa` |
| **FIM-Midtraining-400K**（TIGER-Lab） | 开放 | 代码 mid-training 样本格式标杆：掩码上下文→推理→实现的三段式 + 全程 metadata | `fim-midtraining-400K` |
| **AgentTrove**（open-thoughts，169.7 万条 agent 轨迹） | 开放 | agent 轨迹 schema 标杆：conversations + 验证器输出 + ground truth + judgment + 全程溯源 | `agenttrove` |
| **Smoltalk2-Mid**（SmolLM3 的 MT 子集） | 开放 | 推理 mid-training 的 chat 形态（`<think>` 标签）+ source 字段 | `smoltalk2-mid-{nemotron,openthoughts3}` |
| **MegaMath-Web-Pro-Max**（OctoThinker） | 开放 | **网页→训练文本的形态标杆**：LLM 改写后的干净正文 + 双打分 + 来源元数据 | `megamath-web-pro-max` |
| **Nemotron-Pretraining-Specialized**（NVIDIA） | 开放 | 专项合成数据形态：自带 docstring 与 doctest 的"概念教学文档"式代码 | `nemotron-specialized-code-concepts` |
| **OctoLong cross-repo-code-sample** | 开放 | 依赖扩展样本：扩展前后代码 + 扩展过程量化指标 | `octolong-cross-repo` |
| **pentest-agent-dataset-chatml** | 开放 | ②渗透测试内容形态（CVE 问答型） | `pentest-agent-chatml` |
| **bug-bounty-pentest-en** | 开放 | ②渗透测试报告的结构化形态（多 type 行 + 利用步骤/修复建议/赏金字段） | `bug-bounty-pentest-en` |
| **win-exe-malware-analysis** | 开放 | ①逆向分析的结构化形态：沙箱报告（进程树/签名/MITRE TTPs），**无二进制** | `win-exe-malware-analysis` |
| **Trendyol-Cybersecurity-Instruct** | 开放 | 安全 instruction 形态参照（system/user/assistant） | `trendyol-cybersec-instruct` |
| **MidTool-Mix**（20.3B agentic MT） | **gated** | 最对口的 agentic MT 数据；数据卡已存 `cards/`，schema 详见 notes/03 | — |
| **daVinci-Dev**（PR 上下文+轨迹） | **gated** | 代码 agent MT 数据；数据卡已存 | — |
| **Primus-Seed**（Trend Micro 安全 CPT 种子） | **gated** | **最接近我方场景的安全域原始语料**（厂商官网/漏洞库爬取）；数据卡已存 | — |

> gated 数据集解锁路径：`huggingface-cli login` → 在数据集页面接受条款（MidTool/daVinci 需填机构信息）→ 重跑 `fetch_samples.py`。MidTool 的两个 fastText 质量分类器同样是 gated（README 已存）。

---

## 二、各标杆的关键观察

### 2.1 Dolmino（网页/PDF/代码三路对照）——我方 S1–S3 的输出形态基准

- **schema（W3C-IDO 风格）**：`{text, id, metadata{...}, added, created, source, version}`。正文与元数据同文件但正文不可变，一切分数进 `metadata`。
- **metadata 纪律（StackEdu-FIM 分片最完整）**：`int_score`（FineWeb-Edu 式 0–5）+ `score`（fastText 分）双打分并存；`language`、`length_bytes`、`license_type`（permissive 等）、`detected_licenses`、`repo_name`、`path`、`src_encoding`、`uri`（含 S3 blob 指针）——**每条样本可回溯到原始内容与两次打分**。
- **CC 高质网页分片**：文本为纯文本化结果（观察到的样本是邮件列表归档，格式扁平、无 markdown 装饰）——说明他们的网页抽取优先保内容、轻格式。
- **olmOCR PDF 分片**：双栏学术论文被线性化为顺序文本，标题/作者/摘要保持可读——**PDF 文本化的可接受形态**（表格式内容损失是已知代价）。
- **StackEdu-FIM 分片**：样本存的是原始代码文档，FIM 掩码在训练时套用——掩码模板不落库，落库的是带分数与 license 的源文档。
- **对我们的含义**：S1–S3 的输出先对齐这个形态（text 不可变 + metadata 携带全部分数与来源），v1.2 里"打分与丢弃解耦"的落地参照物就是它。

### 2.2 MegaMath-Web-Pro-Max——"改写后网页"的形态标杆

- schema：`{text, id, cc-path, domain, finemath_score, lang, lang_score, timestamp, url, math_score}`。
- text 是 **LLM 改写后的干净正文**（非原始抽取）：结构化步骤列表、无广告残留、代码与公式内嵌——这正是 Pro-Max"小模型粗筛+大模型改写"管线的产物。
- 对我们的含义：④工具教程、①writeup 的"精修层"输出可参照此形态；`url+timestamp` 必存；`lang/lang_score` 伴随。

### 2.3 FIM-Midtraining-400K——代码 MT 样本格式标杆

- schema：`{messages:[user, assistant], metadata, fim_split}`。
- user = 固定模板（任务说明 + 带掩码文件全文）；assistant = `### Reasoning` + `### Implementation`（```代码围栏```）。
- metadata：`sample_id`、`repo_id`、`repository_url`、`file_path`、`license` 等（见 notes/04 的完整字段表）。
- 对我们的含义：我方 S7b 的 FIM 样本直接套用此格式（模板字节一致原则）；单/组掩码用 `fim_split` 类字段区分。

### 2.4 AgentTrove——agent 轨迹 schema 标杆

- schema：`{conversations, agent, model, date, task, episode, run_id, trial_name, model_provider, original_source, original_teacher, result, trace_source, path, task_binary, instruction, verifier_output, ground_truth, judgment, split}`。
- 三个值得照抄的设计：(a) **验证器三元组** `verifier_output / ground_truth / judgment` 使每条轨迹的可信度可查；(b) **溯源四元组** `original_source / original_teacher / run_id / trial_name` 使合成路径可审计；(c) system prompt 里显式规定**结构化响应格式**（JSON: analysis/plan/commands 批次）——这是 scaffold 对齐（P4）在数据层的体现。
- 对我们的含义：S7c 轨迹样本的 metadata 模板。注意其响应格式是 terminal-bench 风格 JSON 批次，而我方目标是 Claude Code/Codex 双模板——**conversations 的角色/工具结构可参照，响应格式换成我方两种模板**。

### 2.5 安全域 instruction 类（pentest-agent / bug-bounty / malware-analysis）

- `pentest-agent-chatml`：CVE 问答对，assistant 输出 = 结构化 CVE 摘要 + 引用列表（BID/GLSA/MLIST...）——①漏洞 writeup 的"知识问答化"产物形态参照。
- `bug-bounty-pentest-en`：**单文件多 type 行**（`type` 字段区分 methodology/checklist/technique/report-template/qa），每 type 有专属字段（`exploitation_steps`、`payload_examples`、`detection_bypass`、`remediation`、`bounty_range_usd`、`cvss_range`）——②渗透测试报告的结构化形态参照；但内容质量参差（模板化文本多），只作形态参考、不作质量标杆。
- `win-exe-malware-analysis`：沙箱报告 JSON（`behavior` 进程树 / `signatures` / `ttps` MITRE 映射）——①逆向分析的结构化知识形态参照，且示范了"分析报告可以不含任何二进制工件"（对应我方 S6 处置矩阵）。
- 注意：这批数据集都是 **SFT instruction 风格**，不是 mid-training 语料；形态可参照，配比上归入 S7d 知识注入或后训练参考，不进 MT 主池。

---

## 三、跨标杆的共性纪律（我方输出的硬要求）

1. **正文不可变 + 分数旁路**：text 字段只存内容，一切打分/过滤决策进 metadata（Dolmino 模式）。
2. **每条样本可回溯**：来源（url/cc-path/repo+path/uri）、时间（timestamp/added）、license 三件套必须全程携带（所有标杆共同点）。
3. **双打分并存**：通用质量分（int_score）与领域分（fastText score）分开存（Dolmino/MegaMath）。
4. **合成/增强样本必须带溯源与验证**：teacher、模板版本、verifier 输出、judgment（AgentTrove/FIM）。
5. **训练形态对齐目标 scaffold**：AgentTrove 在 system prompt 里硬编码响应格式——我方轨迹必须用 Claude Code/Codex 双模板（P4）。
6. **文本化产出可读性优先**：olmOCR/MegaMath 的输出证明"线性化但保持结构可读"即可，不必追求还原排版。

---

## 四、我方四类数据的输出 schema 建议（对齐 PLAN S7/S9）

统一外层（所有类型共用）：

```json
{
  "sample_type": "writeup|pentest_report|ctf_writeup|tool_tutorial|code_fim|trajectory|state_pair|knowledge_qa",
  "text": "正文（不可变；markdown 规范化；代码用围栏；终端块用标记）",
  "metadata": {
    "id": "内容寻址 id", "url": "", "source_group": "blog|forum|db|doc|pdf|repo",
    "crawl_ts": "", "license": "", "lang": "", "lang_score": 0.0,
    "taxonomy": {"bucket": "vuln-analysis", "confidence": 0.9, "axis": "offensive"},
    "quality": {"domain_score": 0.0, "edu_score": 4, "gopher_pass": true},
    "safety": {"verdict": "keep|redact|drop", "frr_bucket": "", "judge_scores": {}},
    "decontam": {"checked_benchmarks": [], "ngram_hits": 0},
    "images": [{"pos": 12, "caption": "", "ocr_text": "", "hash": "", "kept": false}],
    "provenance": {"pipeline_version": "", "stage_log": ["extract", "score", "dedup"]}
  }
}
```

各类型的 text/结构要点：

| 类型 | text 形态 | 额外 metadata | 参照标杆 |
|---|---|---|---|
| ①漏洞/逆向 writeup | markdown：标题/环境/步骤/终端块/结论；截图位置插 `[图: caption]`+OCR 文本 | `cve_ids[]`, `attack_tactics[]`, `tool_names[]`, `artifact_scan`(无二进制断言) | dolmino-cc-hq + win-exe-malware(结构化部分) |
| ②渗透测试报告 | 结构化段落：scope→findings→步骤→影响→修复；避免可运营工件 | `report_sections{}`, `severity`, `scope` | bug-bounty-pentest-en 字段集 |
| ③CTF writeup | 挑战名/分类/难度→思路→命令-观测序列→flag 处理（赛题 flag 打码） | `ctf_event`, `year`(窗口期规则), `category`, `scaffold_format` | pentest-agent + AgentTrove(轨迹部分) |
| ④工具教程 | 命令/参数/输出/常见错误；每个终端块可独立成命令-观测对 | `tool_name`, `tool_version`, `affordance_profile`(S7a 六字段) | megamath-web-pro-max(改写形态) + MidTool affordance |
| 代码 FIM（S7b 产物） | messages[user 模板+掩码上下文, assistant Reasoning+Implementation] | `fim_split`, `repo_id`, `file_path`, `license` | fim-midtraining-400K 逐字段对齐 |
| 轨迹（S7c 产物） | Claude Code/Codex 双模板 conversations | `scaffold_format`, `verifier_output`, `ground_truth`, `judgment`, `run_id` | agenttrove 元数据模板 |
| 状态对（S7c 产物） | (初始快照→目标观测) + 归一化匹配规则 | `env`, `replay_verified(3x)`, `diversity_key` | State2State（notes/03） |
| 知识 QA（S7d 产物） | 实体锚定 QA；拒绝采样留存 | `entity`, `qa_style`, `reject_rate` | AgentFounder FAS（notes/03） |

> 落地顺序建议：先在 P0 用本 README 的统一外层 schema 冻结 `metadata` 必填集（id/url/source_group/license/quality/safety），P1 起每类数据的 text 形态以对应标杆样本做逐条对照验收。
