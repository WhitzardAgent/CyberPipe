# 调研笔记 04：FIM-Midtraining 与 daVinci-Dev 代码级核验

> 子任务报告存档，调研日期 2026-09-29。两个仓库均已克隆并逐文件核验：`research/repos/FIM-Midtraining`、`research/repos/daVinci-Dev`。

## 一、FIM-Midtraining（TIGER-AI-Lab，arXiv 2607.12463）

### 1.1 结构与流水线（5 步，`data_construction/`）
```
common/step_1_download_repos.py        浅克隆 CSV 里的 968 个 repo（ThreadPool, --depth 1, 4 并发, 300s 超时）
common/step_2_extract_python_files.py  展平为每 .py 一条 JSON 记录（编码回退 utf-8→latin-1→cp1252）
single_function/step_3_select_functions.py + common/dep_graph.py   PDG 打分选掩码目标
single_function/step_4_fim_and_critique.py   Gemini 补全 + 自我批评（唯一花钱步骤，200 分片 kill-safe）
single_function/step_5_prepare_sft_data.py   按批评分过滤、产出 SFT JSONL
multi_function/   同构三步（选 2–3 函数组 / step_4_multi_fim_and_critique.py / step_5）
```
所有路径由 `common/config.py:derive_paths()` 从单一 `config.yaml` 派生；CLI 参数永远覆盖 yaml。**单一 config + 派生路径 + 幂等分片**是可直接搬走的三件套。

### 1.2 核心算法（`common/dep_graph.py`）
**PDG 构建**（`DependencyGraphBuilder`，仅 Python `ast`）：节点=函数/方法，两类边——call 边（含 `self.method`→`Class.method`、类实例化→`X.__init__`、短名模糊匹配 `_short_to_qname`）与同类 sibling 边（`_add_sibling_edges`，双向）。

**复杂度 Ĥ**（`compute_complexity`，权重 w_loc=0.4/w_cc=0.4/w_depth=0.2）：
- norm_loc = min(loc/50, 2)；norm_cc = min(圈复杂度/10, 2)（数 If/For/While/Except/BoolOp/推导式）；norm_depth = min(嵌套深度/5, 2)。

**可推断性 Î**（`compute_inferability`，α=0.30 β=0.25 γ=0.20 δ=0.10 ε=0.15）：
- caller 项 = min(Σ call-site specificity / 3, 1)；specificity：基 0.50，常量实参 +0.15，Name 实参 +0.05，关键字参数 +0.12/个，封顶 1.5，找不到调用点回退 0.5；
- callee 项 = min(文件内 callee 数/4, 1)；签名项：返回类型注解 +0.30、参数注解 +0.25、公开名分词 min(n/5,0.25)、非 self 参数 min(n/6,0.20)；docstring +0.5；类上下文 = min(sibling 数/5,1) + 有同类 `__init__` 再 +0.3。

**综合分与难度惩罚**（`select_targets`）：`fim = h·i/(h+i+1e-8)`；`difficulty = max(0, h−i)/(h+1e-8)`；difficulty > ceiling(0.5) 时乘单边高斯 `exp(−excess²/2σ²)`（σ=0.2）。硬阈值：文件 50–1800 行、函数 10–200 行、`min_complexity=0.15`、`score_threshold=0.08`、跳过约 30 个 dunder。每步打印 loc/complexity/inferability/fim_score/difficulty 的 p10–p90 分布，**调阈值不花钱**。

**多函数组**（`multi_function/step_3_select_function_groups.py`）：8 种拓扑——pair：caller_callee/co_callee/sibling_coupled/mutual_call；triple：call_chain/hub/fan_in/class_triad。组分 = Coupling × 组Ĥ × 组Î/(组Ĥ+组Î) × 难度惩罚；Coupling 权重 call 0.50/sibling 0.20/共享 `self.xxx` 状态 0.30（Jaccard 式）。**组级 Î 重算时把组内信息扣掉**（组内 caller/callee/sibling 不计入，docstring 因会被掩掉故 doc_score=0）——"掩码后信息才公平"的正确建模。上限：mask LOC 占比 pair≤30%、triple≤40%，每文件最多 5 pair/3 triple，贪心去重。

**掩码与校验**：`mask_function_body()` 替换为正确缩进的 `# <MASKED_FUNCTION_BODY>`；`postprocess_results()` 逐条用 start_line/end_line 从原文重新抽取并比对 `func_content`（宽松 rstrip 后仍不等则丢弃）——**防行号漂移的二道校验值得照搬**。

**推理文本**（step_4）：每条样本两次 Gemini（`gemini-3-flash-preview`，fim_temperature=0.7 / critique=0.3，重试 3 次指数退避）。补全 prompt 强制 `### Reasoning` + `### Implementation` 结构；critic 输出 JSON：`feasibility{is_feasible, confidence, infeasible_factors}` + 5 维分（correctness/executability/api_usage/readability/completeness，各 1–5 带 reason）+ `overall_score` + `should_discard`。判据写进 prompt：不可行 OR (overall≤2 且 executability≤2) OR executability==1。**训练 assistant turn = 原始 response（推理+代码一起），user turn 与发送 prompt 字节一致。**

### 1.3 输出 schema（`step_5:construct_sft_sample`）
`{"messages":[{role:user},{role:assistant}], "metadata":{...}}`。metadata：repo 级（sample_id, repo_id, repository_url, file_path, line_num, func_num, category, description, notes, license）、文件级（file_lines, graph_stats）、函数级（func_name, start_line, end_line, loc, complexity, inferability, fim_score, difficulty）、质量级（overall_score, is_feasible, correctness…completeness）。**两条 id 纪律**：CSV 的 `sample_id` 进来就改名 `repo_id`，step_2 重新铸造文件级 `sample_id`，记录键=(sample_id, func_name, start_line)——否则分片 checkpoint 去重会静默碰撞。license 随每条样本走。

### 1.4 训练配置（`midtraining/configs/fim_midtrain.yaml`）
LLaMA-Factory full SFT，cutoff_len=32768，lr=1e-5，1 epoch，cosine，warmup_ratio=0.1，weight_decay=0.05，bf16，有效 batch=128（8×H100，per_device 1×accum 16），DeepSpeed ZeRO-3 + flash_attn fa2 + liger + group_by_length。Qwen3-8B 版加 `rope_scaling: yarn`。数据配比：80% single / 15% pair / 5% triple（400K 样本 ≈2.63B tokens）；`mixing/README.md` 给出 80/15/5 最优的消融依据但**混排脚本未随仓库发布**。

### 1.5 质量过滤（`config.yaml: filters`）
single：5 维每维 ≥3 且 overall ≥4；multi：组内**每个**函数 ≥3、组 overall ≥4、coherence ≥3——一票否决整组。step_5 便宜可反复重跑；step_4 checkpoint 保留 critic 全文，**换阈值重滤不再花钱**。step_5 做特殊 token 清洗（`SPECIAL_TOKENS_TO_REMOVE`），防止污染训练分隔符。

### 1.6 局限
- 只支持 Python（`ast` 写死）；换语言需重写 `DependencyGraphBuilder`（上层打分语言无关）。
- 依赖 Gemini API；step_4 每条 2 次调用，成本主瓶颈。
- PDG 只在单文件内；短名模糊匹配可能连错边。
- 阈值/归一化常数全是 magic number，未做敏感性分析。
- 混排脚本缺失；`should_discard` 靠 LLM 遵守 prompt，代码侧不再校验。

## 二、daVinci-Dev（GAIR-NLP，arXiv 2601.18418）

### 2.1 结构（Go 6-task，`pipeline/`）
单二进制 `pipeline/main.go` 按 `-task repos|prs|enrich|llm_enhance|render|tokenize` 路由；阶段间以 Parquet(Snappy) 目录交接（raw_index/filtered_repos/raw_prs/enriched_prs/llm_enhanced_prs/rendered_text/tokenized_dataset/token_stats，默认 500MB 滚动分文件）。**无 checkpoint：所有 API 请求走本地反向代理缓存**（`cmd/github_api_proxy/main.go`，限流 Retry-After 重映射 + 特殊 GraphQL 端点），重跑靠缓存命中。每 task 30s 打印吞吐监控。

### 2.2 各任务核心逻辑
- **Task1 仓库普查**（`task1_repos.go:enrichAndFilter`）：GitHub API 顺序扫；Language==Python、stars≥5、非 archived；404/451 静默跳过；输出含 `license_key`。
- **Task2 PR 采集**（`task2_prs.go`）：`/pulls?state=closed&sort=created&direction=asc` 分页（按不可变创建时间排序，代理缓存友好）；只留 merged；扩展名白名单 `.py/.pyi/.pyx/.pyw + .md/.markdown/.../.rst`；过滤 1≤py 文件≤5、总文件≤20。
- **Task3 开发上下文重建**（`task3_enrich_pr.go:enrichPR`）：① PR detail 取 base SHA；② changed py files 按 status 分流（removed/modified→基线文件集，renamed→`previous_filename`，added→排除）；③ commits 逐个取 detail，diff 只留 py 文件，**第一个 commit 的 parent SHA**（无则回退 base SHA）作快照点；④ contents API（base64）取快照点文件全文 → `relevant_files`；⑤ git trees recursive 取全仓 py 文件树（413 时降级顶层目录）；⑥ GraphQL closingIssuesReferences 取首个关联 issue + 总数，comments 拉满 100 条。
- **Task4 LLM 增强**（`task4_llm_enhance.go`）：OpenAI 兼容端点（自托管 `Qwen/Qwen2.5-Coder-32B-Instruct`，temperature=0.7/top_p=0.9）；PR 摘要（1–4 句，max_tokens=512）+ 逐 commit 消息改写（patch 截断 2000 字符，max_tokens=256）；**单 commit 失败回退原消息，不弃样本**。
- **Task5 渲染**（`task5_render_text.go`）：diff patch → 结构化编辑（`diff/types.go`：str_replace/insert/create/delete/rename）。核心 **context expansion**（`diff/context.go:ExpandContext`）：old_str 不唯一时向上/下各扩最多 `DefaultMaxContextExpand=20` 行直到唯一（实测 10 行→99.5%、20→99.8%、30→99.9%）；`TranslatePRDiffs` 维护 fileContentMap 并逐 commit 应用编辑。模板：`# Repository Context` → `# Issue` → `# Pull Request` → `# Relevant Files Found`（逐文件 fenced code，>50 文件截断）→ `# Edits`。全文过 `sanitizeUTF8`。
- **Task6 过滤+分词**（`task6_tokenization.go`）：Stage1 过滤 `AuthorType=="Bot"` 与 12 个 SWE-bench 仓库黑名单（`config/config.go:SWEBenchRepos`）；(RepoID,PRID) 去重；关联 issue 评论 >20 丢弃；Rust worker 分词（Go↔Rust MessagePack IPC，128 线程，22M tokens/s）；**>32000 tokens 丢弃**；输出含 token_stats，打印 8K/16K/32K/64K/128K 保留率。

### 2.3 环境轨迹侧（`env_traj_utils/`）
`convert_trajectories.py`：GLM-4.6 SWE-agent 原生 tool_calls → XML function calling（`<function=bash><parameter=command>…`），`reasoning_content` 包进 `<think>`，system 消息替换为内置 XML 版，tool 角色改 user。`tokenize_trajectories.py`：HF tokenizer 批量分词、按 `--max-tokens`（131072）过滤、分片 parquet。**MT 训练超参不在本仓库**（查论文）。

### 2.4 局限
- Python-only；无多模态/图片处理路径。
- 依赖自建 GitHub API 反向代理；推荐 100+ 核工作站。
- 去污染仅 12 个硬编码仓库名；无 embedding 去重/PII/语言检测。
- LLM 采样参数、patch 截断、评论上限散落硬编码。

## 三、可移植性

**直接可搬**：
1. FIM 的"便宜静态打分 → 贵 LLM 打分"两级漏斗 + Ĥ·Î/(Ĥ+Î)+难度单边高斯打分族——把"函数"换成"页面中可预测的区块/代码片段"，Î 五因子可逐项类比（调用点→引用点、内部被调→内部链接、签名、文档、类上下文→模板/站点上下文）。
2. FIM step_4/5 全部工程：确定性 unique_id、逐条原子 checkpoint（tmp+rename）、200 分片 kill-safe、critic JSON schema（feasibility 先行 + 5 维分 + should_discard 判据写进 prompt）、checkpoint 留全文以便免费重滤。
3. FIM 双 id 纪律、license 逐样本透传、特殊 token 清洗列表、"训练分布=打分分布"字节一致原则。
4. daVinci 的 context expansion（20 行，99.8% 唯一化）——把 diff/日志改写成 str_replace 式可执行编辑语料；"边应用边更新文件状态"适合多轮网页内容演化重建。
5. daVinci 的代理缓存替代 checkpoint、按不可变字段排序提升缓存命中、Bot/黑名单/评论数/token 上限四级廉价过滤、Go(IO)+Rust(CPU) MessagePack IPC 分词、每阶段 Parquet schema 集中单文件。

**需改造**：FIM 掩码单位（函数体）→ 网页自选（代码块、属性-值对、表格单元格）；daVinci 的 issue/PR 结构 → 抓取时间戳/页面树；两者过滤全是文本启发式，图文交错数据的图片质量/图文相关性过滤均未提供，需自建。

**不可搬**：FIM 的 Python ast PDG；daVinci 的 GitHub GraphQL 约定与 Python 扩展名白名单；两仓库都没有多模态管线与通用去重/PII 环节——移植时最大空白。
