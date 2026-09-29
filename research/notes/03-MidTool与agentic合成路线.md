# 调研笔记 03：MidTool / AgentFounder / State2State——agentic mid-training 数据构造

> 子任务报告存档，调研日期 2026-09-29。所有细节来自论文 HTML 全文 / ar5iv / HF 卡片；未获取字段明确标注"未披露"。

## 一、MidTool（Snowflake/UW，arXiv 2608.20314，2026-08）

总量 **20.3B tokens / 1122 万样本 / 42.7 GB**，全英文。

### 1.1 数据混合组成
| 子集 | 原始/增强 tokens | 样本数 | 占比 | 来源 |
|---|---|---|---|---|
| web | 4.4B / 4.1B | 686 万 | 42% | FineWeb（CC 2020–2025）技术页面 |
| pdf | 2.6B / 2.1B | 134 万 | 23% | FinePDFs 英文子集 |
| code | 3.8B / 1.5B | 260 万 | 26% | GitHub 两路：GH Archive 的 agent/MCP 仓库 + 高质量仓库（8 语言组），带 benchmark 仓库黑名单 |
| native-agent-traj | 1.8B | 42 万 | 9% | 真实 REST API + MCP skill 合成轨迹 + AWM rollout + Nemotron 过滤 |

- 增强比例（源 / +QA / +QA+轨迹）：web 36.4%/52.2%/11.3%；pdf 30.8%/13.4%/55.7%；code 68.9%/4.2%/26.8%（PDF 最重度增强，code 最轻）。
- native-agent-traj 细分：nemetron-agentic 335,122；api-traj 48,975；awm-rollout 23,135；skill-traj 17,540。
- 涉及 **260 万唯一工具名，37.2% 领域长尾**。原生轨迹平均 4.0 turns（max 69）；PDF 轨迹平均 7.1 assistant 步、4.8 次工具调用（max 78）。
- Schema：全子集带 `text`；web 加 id/url/dump/date/language_score；pdf 加 ocr_quality_scores；code 加 owner/repo/relpath/sha256/commit_sha（**secrets 用 `<SECRET>` 哨兵替换**）；traj 加 extra/src。轨迹用 chat 模板。

### 1.2 四阶段清洗管线（web/PDF）
1. **高召回预筛**：关键词 + URL 规则，偏向"类代码结构"文档。
2. **fastText 质量分类器**（两个已开源，Apache-2.0）：种子从 100 万 web + 300 万 PDF 抽样，**Qwen2.5-7B-Instruct** 标注；正类：documentation、tutorials、configuration、debugging traces、code-centered technical discussion（web 版含 API references、SDK docs、CLI help、troubleshooting、developer Q&A）；负类：非技术或"对工具使用无价值"；**PDF 用更严阈值**（未披露数值）。
3. **统计质量过滤**：语言置信度、长度、词数、符号密度、估计代码比例；PDF 另加 OCR 质量过滤；code 用 StarCoder 启发式（行数、平均/最大行长、字母占比）。
4. **去重**：SHA-256 精确 + MinHash LSH。

### 1.3 基于原始网页的增强（context-grounded augmentation）——核心方法
- **标注模型：Qwen3-235B-A22B-Instruct-2507**（轨迹合成再加 GPT-5/5.1/5.2）。对每个保留文档产出：质量分 + **结构化 affordance profile**：①能否从文档推断出工具响应（可验证性）；②schema/API 结构证据；③code/CLI 用法；④工作流结构；⑤工具拓扑；⑥领域术语。
- **低质文档保留原文但不增强**（不丢弃，维持多样性）。
- **规则式 planner**（非 LLM 规划）决定增强量：监督量与质量分挂钩、QA 类型预算有界、**每篇文档最多一条多轮轨迹链**。
- QA 类别 = 原子能力分解：工具选择、schema 对齐的参数抽取、格式受限调用、工作流识别、多次/并行调用。
- 轨迹类别：顺序执行、参数澄清追问、工具切换、长上下文推理。
- **幻觉过滤**：QA/轨迹须通过解析 + 语义质量控制；工具源轨迹严格校验 turn 顺序、schema 对齐、必需参数齐全、工具响应一致性；不合格**带 QC 反馈重试一次**，仍不合格丢弃。Prompt 原文未披露。
- 工具侧：工具清单解析后预筛低信号源，**GPT-5 打质量分 + 可行性 profile**（轨迹族三型：简单单调用 / 复杂多次并行 / 信息缺失——后者专门训练"从残缺信息恢复"）。

### 1.4 训练与评测协议
- Mid-training：Qwen3-4B/8B-Base，**1 epoch**，ArcticTraining，32×H200；seq len 8192，AdamW LR 3e-5，wd 0.01，**WSD 调度**，50 warmup 步，全局 token batch 4M，packing。
- 后接 SFT：10 万条 TOUCAN 子集，seq 32768，LR 2e-5，cosine（warmup ratio 0.001），batch 128。再接 RL：8×B200，AWM 框架（**526 个合成工具环境**），GRPO，64 步，LR 1e-6(4B)/5e-7(8B)，16 rollouts/prompt，KL 0.001，entropy 0.0，clip-high 0.28，history limit 3，max 20 agent turns。
- 评测（AWM harness，thinking 关闭）：**对照组 = 同一 base + 同一 SFT/RL 配方，仅去掉 mid-training**。BFCLv3：4B 39.73→50.25→(RL)54.18；8B 47.62→55.12。τ²-Bench 4B Pass@1 8.54→19.96。MCP-Universe 4B 13.20→23.80。
- **消融（Table 6，4B+SFT，Δ vs 无 mid-training）**：仅清洗数据 +2.6 BFCL；+原生轨迹 +7.9（但 τ²/MCP 反而降）；+context-grounded 轨迹 +4.9（multi-turn +5.5 最大）；**完整混合才使 8 项指标全部提升**（BFCL +10.5，τ² +3.7，MCP +5.5）。Dolmino-20BT 迁移差（MCP −7.8）。结论：两类轨迹数据互补，缺一不可。
- 其他：mid-trained 模型 SFT loss 更低、RL 早期适应更快；MCP-Universe web-search 子集恒为 0 → 深搜索行为需专门数据；DeCon 污染审计 <20 个候选全为误报。

### 1.5 可迁移到网络安全管线
- **fastText 正负类定义直接套用**：正类改"安全工具文档/漏洞通告/渗透 CLI 用法/IDS 规则/加固配置/调试 trace"，负类"与工具使用无关的资讯页"；种子用 Qwen2.5-7B-Instruct 自动标注，PDF 更严。
- **affordance profile 六字段**改造成"网络安全 affordance"：能否推断出工具/命令输出、命令行/配置结构证据、攻击或取证工作流结构、工具依赖拓扑、术语表——把通用网页变成 agent 教材的关键中间表示。
- **规则式 planner 控制增强预算**（质量挂钩、每文档 ≤1 条多轮链、QA 类型有界）直接可用。
- **轨迹族三分法**对应安全场景：单命令执行 / 编排链（侦察→利用→驻留）/ 参数缺失追问。
- 增强比例参考：重清洗轻增强（code 68.9% 仅原文）、PDF 重度增强（55.7% 全链）。
- **消融结论"仅清洗数据对 agentic 指标几乎无效、必须加轨迹"提示：清洗管线产出要预留 9% 左右的轨迹槽位。**
- 工程细节：secrets 哨兵替换、benchmark 仓库黑名单、DeCon 事后审计。

### 1.6 不可迁移
- 具体阈值全部未披露（fastText 阈值、质量分界、planner 规则、prompt 原文）。
- 20.3B/1 epoch/4M batch 对垂直领域过大；安全语料可能只有 1–3B token 量级。
- 工具生态是 REST/MCP 通用 API；安全工具多为 CLI/交互式 shell（Metasploit、nmap），原生轨迹格式需重设计。
- 数据集 gated。

### 1.7 代码仓库
**无官方 GitHub 仓库**。发布物全部在 HF org `MidTool`：gated 数据集 MidTool-Mix、两个 fastText 分类器（Apache-2.0）、模型 Arctic-MidTool-{MT,RL}-{4B,8B}。

## 二、AgentFounder / Tongyi DeepResearch（阿里，arXiv 2509.13310，2025-09）

从 Qwen3-30B-A3B-Base 做 **~300B token Agentic CPT**（缩放实验到 315B）。

### 2.1 合成数据分类体系
**FAS（First-order Action Synthesis，无监督信号，Stage 1 主体）**：
1. **Knowledge-to-Question**：静态源（历史轨迹、工具调用结果、CC、Wikipedia）→ **实体锚定的开放世界知识记忆**（entity 为 key → 改写陈述句）；第二阶段采样实体簇生成**多风格问题**：事实检索、数值计算、多跳推理、综合题。
2. **Planning Action Synthesis**：对 query 生成 K 个多样问题分析 + 首步动作预测，**不实际调 API**；技巧是"K 个共享同一知识记忆但风格不同的问题"；QC = 知识对齐验证的拒绝采样（LLM-as-Judge）——拒绝 43.5% 后准确率 50%→82%，Content Inconsistency 占拒绝的 26.2%。
3. **Reasoning Action Synthesis**：两步——分解问题出初步答案 A1；给定 Q+必备知识精炼 A2。**全程禁止外部工具调用**；LLM-as-judge 拒不对齐样本。

**HAS（Higher-order，有监督信号，复用判分轨迹）**：
1. **Step-level scaling**：对每步上下文生成 N 个备选 "thought + invocation"（**不执行工具**），(N+1)×K 决策空间。
2. **Contrastive decision-action synthesis**：轨迹改写成显式多选项选择题，正文插 "I will choose option nk"，后接真实响应，末尾 "My decision is {Correct/Incorrect}"。**目标从轨迹模仿转为逐步决策**，规避 step-level reward 工程。

### 2.2 两阶段
- Stage 1：~200B tokens，agent 数据 + 知识推理语料混合，32K context，FAS 为主 + 短 HAS。
- Stage 2：100B tokens 精选高质量 agent 数据，**context 扩到 128K**（HAS 为主）。

### 2.3 关键消融
- 数据类型（SFT-A 后训）：无 CPT 26.9 BC-en；仅 FAS(50B) 31.4（BC-zh +9.0%）；FAS+HAS 31.4/40.1。FAS 提升最大。
- 两阶段 vs 单阶段：Pass@1 +3.3%，Pass@3 +3.7%。
- 可适配性：三种不同后训数据下均稳定 +5.75~6.45%——CPT 与下游配方解耦。
- 数据缩放：**对数增长，前 15B token 贡献最大（+3.8%）**，315B 累计 +8.0%。
- CPT 后 SFT loss 0.8656→0.7953；Pass@1 31.5%→Pass@16 75.8%——CPT 打开可被 RL/采样释放的上限。

### 2.4 可迁移
- **实体锚定知识记忆**适合安全语料：实体 = CVE 编号、工具名、漏洞类型、ATT&CK 技术 ID；从 CVE 描述生成"事实检索 + CVSS 计算 + 多跳（漏洞→补丁→绕过）+ 综合"四类问题。
- **禁止工具调用的纯知识推理合成**是安全知识注入的低成本路线。
- **对比式决策合成**可改造为：多候选命令/利用路径选择 + 自我判定。
- 拒绝采样参考：LLM-judge 拒收 ~43% 才能把准确率 50%→82%。
- 缩放规律：安全 CPT 不必贪大，先保证前 10–20B token 的质量与密度。

### 2.5 不可迁移
- 300B 级 30B-A3B MoE 预算；FAS 依赖海量历史 agent 轨迹/搜索日志。
- 混合比例（agent 数据 vs 知识语料）未披露。

## 三、State2State（THUNLP-MT，arXiv 2608.04934，2026-08）

**不写任务，只造状态对**——从环境随机探索取 (初始状态 s₀，目标观测 o*)，构造可验证状态转移任务做 mid-training（RL，非 next-token）。

### 3.1 构造流程
1. **随机探索器**（刻意不用 LLM：LLM 先验偏置到人类任务型状态且贵）：每步从合法动作集采样，允许轻先验（前期偏导航、后期偏操作）。ScienceWorld 2,560 episodes ≤300 步，**explore-then-operate 前 20% 空间探索 / 后 80% 改状态**；ALFWorld 256 环境×20 批=5,120 条轨迹 ≤500 步，动词加权采样；目标只取步数 ≥10 的观测，黑名单子串过滤报错。
2. **目标过滤与多样性采样**：黑名单过滤无信息观测；每唯一观测至少取一次、单观测重复上限 5；ScienceWorld 8,000 目标全唯一。
3. **可达性回放验证**：每目标从同一初始配置**回放 3 次**，只保留能一致到达的观测。
4. 任务格式：prompt 要点 "reach the following TARGET STATE (the environment observation text must match it)"；`<think>` + `<action>`。
5. **验证器 = 纯规则无 LLM**：r=1 iff 归一化精确匹配；GUI 用"对策略隐藏的 XML 结构相似度 + 截图相似度"。

### 3.2 数据量与训练
| 环境 | 任务数 | 中位目标长 |
|---|---|---|
| ScienceWorld | 8,000 | 72 字符 |
| ALFWorld | 4,256 | 44 字符 |
| MobileWorld | 365 状态 | — |

GRPO + DAPO 动态采样，**仅 80 步 mid-training**；LR 1e-6，KL 0.01。结果（Qwen3-8B）：ALFWorld 75.21→97.45（S2S+RL）；ScienceWorld 31.50→56.00。**SFT→S2S→RL 最优**。跨环境迁移：ScienceWorld 状态任务迁移 ALFWorld 89.44 > 人类任务 RL mid-training（86.87）——状态任务比人类任务更可迁移。

### 3.3 可迁移到安全
- 靶场（CTF 平台、DVWA/WebGoat、shell 沙箱、SIEM 控制台）跑随机/脚本化探索，把可复现环境状态（ls 输出、nmap 报告、登录后页面 DOM）存为观测，配成 (初始快照→目标快照)。
- 验证器照搬：终端输出规范化后归一化精确匹配；回放 3 次验证；多样性配额防退化。
- explore-then-operate（20%/80%）适配"先侦察后操作"。
- 数千级任务即有效，不需要百万级。

### 3.4 不可迁移
- 只覆盖"到达已知终态"，不含漏洞利用创造性。
- 依赖可确定性重置的环境；ASLR/时间戳/动态页面需先做状态规范化。
- 通用域动词空间远小于安全 CLI，动词加权表需按安全命令分布重造。

## 四、三线汇总
1. **清洗层**（MidTool）：关键词预筛 → 领域 fastText（LLM 自动标注种子）→ 统计过滤 → MinHash，已验证的四段式；阈值自调，PDF 更严。
2. **增强层**（MidTool + AgentFounder）：affordance profile 接地标注 + 规则 planner 预算控制 + QC 重试一次丢弃；实体锚定记忆生成多风格问题；判分轨迹对比式决策改写。LLM-judge 拒收 ~40% 是参考强度。
3. **配比经验**：MidTool 轨迹占 9% 且两类轨迹必须齐全；AgentFounder 前 15B 收益最大；State2State 数千任务、80 步即可。建议先小规模复现 MidTool Table 6 式增量消融。
4. **公开资产**：MidTool 两个 fastText 分类器可下载（Apache-2.0）；AgentFounder 与 State2State 无代码/数据发布。

来源：arXiv 2608.20314 | 2509.13310 | 2608.04934 | HF MidTool collections
