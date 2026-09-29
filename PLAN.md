# 网络安全 Mid-training 数据管线实施方案

**版本**：v1.2（2026-09-29；v1.1 纳入：①基座为多模态模型，②目标 agent scaffold = Claude Code / Codex。v1.2 纳入第三项决策：③图文数据落点 = "文本为主、图文为辅"双轨，论证见 6.3 与 `research/notes/06`）
**目标**：面向网络安全网页数据（代码、图文交错两类），建立一条高质量 mid-training 数据清洗与重构管线，服务于**下游 agentic 能力**（工具使用、多步操作、环境交互）的提升。
**依据**：对 25+ 项公开工作的调研与 4 个代码库的代码级核验，报告存档于 `research/notes/01–05`，参考代码在 `research/repos/`。

---

## 0. 一页结论（TL;DR）

1. **纯清洗不产生 agentic 收益**。MidTool 的消融（Table 6）显示：同样的 token 预算，只用清洗后的网页数据对 BFCL 仅 +2.6，加入 context-grounded 增强数据与原生轨迹才全指标提升。因此本管线 = **清洗骨干 + agentic 导向重构层**，且从设计之初就为"轨迹类数据预留 ~10% 槽位"。
2. **agentic 能力无法用静态数据替代**。CWM Table 4：PR/静态代码把 agentic NLL 从 0.39 只降到 0.37，环境交互轨迹才降到 0.29。管线中必须有一条"环境轨迹"支路（沙箱探索产生的状态对任务、或 writeup 重建的命令-观测对），哪怕量小。
3. **图文数据"文本为主、图文为辅"（已定决策）**：安全数据 100% 文本化（OCR/caption）进入 mid-training——现有 agentic mid-training 证据链（MidTool/CWM/Kimi-Dev/AgentFounder/State2State/FIM/daVinci）全部建立在文本观测上，且目标 scaffold 的 in-loop 观测就是文本 tool_result；图像分支降级为"数据资产生产线"（过滤/OCR/caption/存储照常建设，交错开关保留），另设通用多模态回放 3–5% + 可选安全截图切片 0–2% 保护基座视觉通路。终端截图 OCR 仍必须并入文本流与所有过滤器（质量、安全、去污染）。
4. **打分与丢弃解耦**：每个过滤/评分阶段只产生分数写入 metadata，阈值后置（dolma attributes 模式）。领域数据稀缺（预估全量高质安全网页仅 1–5B token），任何"先扔后想"都不可逆。
5. **混合骨架采用 CWM 三段式**：~30% 领域专项（含轨迹）+ ~40% 通用代码/仓库级 + ~30% 通用回放；领域数据**早引入、高权重**（CMU），**放在 MT 阶段而非后训练**（PRISM）。
6. **验证协议先于数据生产**：固定后续训练的对照消融（MidTool/daVinci/FIM 的共同协议）+ microanneal 选源法（Dolmino）+ 按能力族分组的评测（CWM）。先在 4–8B 模型上跑通闭环，再扩量。
7. **轨迹与编辑语料对齐 Claude Code / Codex 两种 scaffold 格式**（已确认）：两者的动作面都是 bash + str_replace 编辑 + 文件读取 + 搜索，工具面小且稳定——轨迹合成只需覆盖这一套工具、按双模板混训；agentless 编辑语料统一 str_replace 形态；私有评测直接跑在同构 scaffold 上。

---

## 1. 目标定位与设计原则

### 1.1 Mid-training 阶段定位

- 输入：base 模型（广泛预训练后）；输出：具备安全领域知识与 agentic 基础先验的模型，供后续 SFT/RL 使用。
- 训练目标保持 next-token LM（可含 packing），不做任务化指令格式——这是 MidTool（1 epoch、8192 ctx、WSD）与 SmolLM3（SFT 形式但数据为推理语料、32K ctx、packing）的共同形态。
- 目标 token 预算：**首轮 20–50B**（PRISM 显示通用推理混合 15–27B 即饱和；AgentFounder 显示前 15B token 贡献最大收益；MidTool 用 20.3B）。扩量决策基于消融。

### 1.2 从调研中提炼的五条设计准绳

| 准绳 | 出处 |
|---|---|
| P1 数据要"留到后续训练仍有效"：所有数据组件必须能通过"固定后续训练"的消融检验 | OctoThinker、daVinci、FIM、MidTool 共同协议 |
| P2 每类数据映射到各自能力族，单指标会系统性误判（PR 涨 oracle-NLL 不涨 agentic-NLL） | CWM Table 4 |
| P3 自然数据为主体，合成只做最小必要 + 上采样；过合成导致过特化 | Qwen3-Coder-Next |
| P4 跨 scaffold 迁移有限：轨迹数据格式以**我方目标 scaffold**为主，混少量他格式 | Qwen3-Coder-Next Fig 3 |
| P5 负结果约束设计：长 CoT 有冗长副作用（OctoThinker）、蒸馏有推理-事实取舍（Meta）、对齐 MT 有 OOD 泛化限制（OpenAI）→ 推理增强要克制、评测要含 OOD | 调研第七节 |

---

## 2. 总体架构

```
                         ┌─────────────────────────────────────────────────┐
                         │  S0 采集/接收  seed-list 定向爬取 + CC/GitHub/CC-PDF 回收 + PDF 白皮书 │
                         └───────────────────────┬─────────────────────────┘
                                                 ▼
   ┌──────────────────────────────── S1 抽取与规范化（文本/代码分支）───────────────┐
   │  WARC/HTML → DOM 保序遍历 → <pre>/<code> 预切（占位符）→ trafilatura 正文 → 回填围栏代码块 │
   │  → Markdown 规范化（标题/列表/表格/终端块）→ 原始 HTML 存 metadata           │
   └──────────────┬───────────────────────────────────────────┬──────────────┘
                  ▼                                           ▼
   ┌── S2a 图文分支（文本化为主+资产线）┐        ┌── S2b 纯文本/代码分支 ──────┐
   │ 图像下载/基础过滤/NSFW/去重    │            │  （并入主流）                │
   │ PaddleOCR(终端/代码截图)      │            └──────────────────────────┘
   │ VLM caption(拓扑/流程图)      │
   │ 图文对齐门控/交错比控制        │
   └──────────────┬───────────────┘
                  ▼
   ┌── S3 质量过滤栈（打分与丢弃解耦，全分数入 metadata）────────────────────────┐
   │ 规则(Gopher/lid/符号密度/代码占比) → 领域 fastText → FineWeb-Edu 式 0–5 分   │
   │ → （二期）MIRA 式源感知评分器                                            │
   └──────────────┬────────────────────────────────────────────────────────┘
                  ▼
   ┌── S4 领域分类 taxonomy（~10 桶 × 攻/防标记，multi-label）──────────────────┐
   └──────────────┬─────────────────────────────────────────────────────────┘
                  ▼
   ┌── S5 去重与污染控制 ───────────────────────────────────────────────────────┐
   │ URL 归一/SHA 精确 → MinHash(5-gram,9桶) → 代码块级去重 → 图像 pHash        │
   │ → 评测集去污染（13-gram + 嵌入 + LLM 复核；CTF 窗口期过滤）                 │
   └──────────────┬─────────────────────────────────────────────────────────┘
                  ▼
   ┌── S6 安全合规 ── 双用途过滤（LLM-judge 三轴 + 工件正则 + FRR 校准）+ secrets + PII + license ─┐
   └──────────────┬─────────────────────────────────────────────────────────────┘
                  ▼
   ┌── S7 agentic 导向重构（只有通过 S3–S6 的高分文档进入）───────────────────────────────┐
   │ 7a affordance profile + 规则 planner + QC 重试（MidTool 式增强：QA/命令-观测/轨迹）     │
   │ 7b 代码侧：多语言 FIM（PDG 式打分）+ 仓库级组织 + 多序列化格式                         │
   │ 7c 环境轨迹：沙箱随机探索 → 状态对任务（State2State 式）；writeup → 命令-观测重建         │
   │ 7d 知识注入：实体锚定 QA（CVE/ATT&CK/工具实体）+ 对比式决策样本（AgentFounder 式）        │
   └──────────────┬─────────────────────────────────────────────────────────────────┘
                  ▼
   ┌── S8 混合与训练阶段（配比/epoch/衰减/长上下文课程）──→ S9 打包与版本化（parquet/webdataset + manifest）
                  ▼
   ┌── S10 评测与消博协议（microanneal 选源 → 4–8B 消融 → 固定后续训练对照 → 能力族评测）──┘
```

横向贯穿：**元数据与血缘**（每条样本记录来源、时间、许可证、全部分数与过滤决策）、**阶段幂等与断点**、**配置驱动**（单 config + 派生路径，FIM 模式）。

---

## 3. 各设计点详细考虑

### S0 数据源与获取

**决策：seed-list 定向爬取为主、Common Crawl/GitHub 回收为辅、PDF 单列。**

- 定向源（安全域的"头部质量"集中处）：NVD/CVE（Public Domain / MITRE ToU）、GitHub Advisory（CC-BY-4.0）、安全厂商博客、CTF 平台公开 writeup 归档、工具官方文档（nmap/Burp/Metasploit/ImmDBG 等）、MITRE ATT&CK/CAPEC、会议 slide/白皮书 PDF。
- 回收源：CC 抓取（用 S3 的 fastText 分类器高召回预筛）、GitHub 高星安全仓库（daVinci 模式：stars≥5、非 archived、license 字段随样本走）。
- PDF 白皮书/报告是安全域特有的大头（MINT-1T 证明 PDF 值得单列；FinePDFs 是 MidTool PDF 子集来源）。Exploit-DB 类受严格 ToS 约束的源**默认不抓原文**，走摘要化路径（S6）。
- **具体考虑**：
  - 爬取遵守 robots/ToU，记录抓取时间戳；seed-list 用 Primus 方法（官方 dump + LLM 筛选目录页 + 专家补录）冷启动。
  - 每个 URL 记录 `source_group`（博客/数据库/文档/论坛/PDF…），它是后续一切源感知处理（评分阈值、清洗规则、配比）的 key——MIRA 与 Primus 都证明"逐源阈值"显著优于全局阈值。
  - 规模预估：按 Foundation-Sec-8B（5B token 语料成模型）与 Primus（2.57B FineWeb 子集）推算，**高质安全网页全量约 1–5B token**；因此本管线每个 token 都贵，"打分后置阈值 + 稀缺源多 epoch（Dolmino 上采样封顶 7×）"是主策略。

### S1 HTML 抽取与规范化（文本/代码分支）

**决策：自定义"预切-回填"式抽取器，输出结构化 Markdown；trafilatura 裸用不可接受。**

- 代码级核验结论（笔记 01）：trafilatura 2.0 会把 `<pre><code>` 压平成单行、无围栏无换行、且没有代码块参数——对代码密集的安全页面是硬伤；resiliparse `preserve_formatting=True` 保留块级格式但同样无代码语义。
- 实现路径（datatrove `BaseExtractor` 子类）：
  1. lxml 解析，DOM **保序遍历**（OBELICS 的核心要求：文本块、`<pre>`、`<img>` 的相对顺序就是训练序列的骨架）；
  2. `<pre>/<code>` 节点抽出 → 占位符替换（记录语言提示、缩进）；
  3. trafilatura（`favour_precision=False` 保召回）抽正文 → 占位符处回填 ``` 围栏代码块；
  4. Markdown 规范化：标题层级、列表、表格转 markdown；**终端会话块**（`$ cmd` + 输出）识别为独立类型并打标——它是 S7c 命令-观测重建的原料；
  5. 原始 HTML 压缩存 metadata（或旁路存储），保留重抽取路径（MegaMath Stage-3 同款思路）。
- **具体考虑**：
  - 抽取质量决定下游一切，此阶段要配一个人工抽检面板（每源组 50 页对账"原文 vs 抽取结果"），这是最便宜的 QC。
  - 论坛型页面（StackExchange、Reddit）走专用模板抽取而非通用 trafilatura。
  - 语言 ID（fasttext lid.176，阈值 0.65）标注 en/zh，不硬丢小语种——安全语料中文内容有价值且稀缺。

### S2a 图文数据处理分支（v1.2 定稿：文本为主、图文为辅）

**决策（论证见 6.3 与 `research/notes/06`）：安全数据 100% 文本化进入 mid-training；图像分支按"数据资产生产线"建设（过滤/去重/OCR/caption/存储照常做，交错开关保留）；另设通用多模态回放 3–5% 与可选安全图文切片 0–2%（由 S10 实验 2 决定）。**

- **证据要点**：agentic MT 的全部公开证据为纯文本（MidTool 连 PDF 都 OCR 文本化）；Claude Code/Codex 的 in-loop 观测是文本 tool_result，图像只在用户主动贴图时出现；交错对文本能力中性（MINT-1T/OmniCorpus）但买到的是多模态技能而非 agentic 能力；图像 token 是文本的 3–10 倍，会挤占已被证明有效的轨迹/FIM/仓库级预算。
- **图像类型分流**：
  - 终端/代码截图（安全页面图像大头）：OCR 文本化，保真率预期 >90–95%（S10 实验 1 实测确认）；
  - 拓扑图/架构图/流程图：VLM 结构化描述文本化——真多模态内容，但终端 agent 的工作流里以命令输出形态出现，默认不交错；
  - 所有 OCR/caption 文本进入文本流与全部过滤器（质量、安全、去污染）。
- **输出形态**：
  - 默认（纯文本）：图像替换为 `[图: caption]` + OCR 文本块，保留位置——进入文本主流。
  - 资产形态（交错，按需启用）：交错序列 = 文本块 + 图像占位标记（携带 URL、caption、OCR 文本、宽高、图注关联），原图打包 webdataset 分片；训练侧用**基座模型自带的 processor/模板**做分辨率与 tiling 处理，管线不做破坏性预裁剪；图像占位 token 必须遵循基座的 image token 约定，否则数据无法被消费。
- **多模态约束（对资产线与切片仍然适用）**：
  1. **图像 token 预算**：一张 1024² 图通常消耗数百至上千 token——多模态份额按 token（而非文档数）设额，配比前先拿基座 processor 实测自家图像的 token 分布；
  2. **视觉塔训练策略**：mid-training 冻结或低 LR 训 vision encoder，跨模态 grounding 主要发生在 LLM 侧——caption/OCR 文本质量是主要杠杆；优先保留信息密度高的图（终端截图、拓扑图、代码截图、补丁对比图），装饰图/广告图已由过滤层剔除；
  3. **对齐门控与图像审查**：RealScore/CLIP 式对齐分低于阈值的图文对降权或解绑（切片启用时模型真实消费像素，错位图文对伤害大）；NSFW 与双用途图像审查（S6）必选。
- 图像处理子步骤（全部按文档级联动的 OBELICS 主张）：
  1. 基础过滤：分辨率 ≥126×126、宽高比 1:3–3:1、<4MB、单页 <25 张（OBELICS 原值起步，再按安全域统计调整）；
  2. CLIP 嵌入上训线性分类器去图标/广告 banner/meme（OBELICS 方法）+ CLIP-based NSFW 检测器；
  3. 去重：ViT-B/32 或 pHash，嵌入距离 <0.05 视为重复（OBELICS）；
  4. **OCR 分引擎路由**：终端/代码截图 → PaddleOCR 批量（便宜、按坐标还原阅读序）；拓扑图/流程图/架构图 → VLM 结构化描述（OCR 无结构概念）。调研确认没有终端截图 OCR 的公开对比基准（ScreenParse 是最近的界面密集解析基准）——**先自建 500–1000 张安全截图内部评测集再定引擎**；
  5. caption：alt-text 缺失/低质（安全站常态是 `image.png`）时用 VLM 重写 caption（IDEFICS2/re-caption 一致结论）；
  6. 图文对齐门控：CLIP/RealScore 式对齐分，低于阈值的图文对降权或解绑（防止错位图文教坏 grounding）；
  7. 交错比控制：统计 images-per-1000-token 分布，分位截断（无公开统一标准，按自家数据分布定）。
- **具体考虑（安全域特有）**：
  - **终端截图 OCR 是本分支价值最高的信号**：writeup 里的关键命令与输出常只在截图里；OCR 文本必须进 S5 去污染库（截图里常有 flag）和 S6 双用途正则库（截图里常有凭据/基础设施信息）。
  - 漏洞复现截图（含 payload/报错）默认保留分析价值，武器化工件按 S6 处理。
  - 成本控制：OCR+VLM 是管线最贵的 CPU/GPU 环节之一，只在 S3 质量分 ≥ 阈值的文档上运行（先筛后算）。

### S3 质量过滤栈

**决策：五层漏斗，所有分数存 metadata、阈值统一在配置中心后置调整。**

| 层 | 内容 | 起点 |
|---|---|---|
| L1 规则 | Gopher 13 条 + 行/字符重复 + 符号密度 + 代码占比（过高=纯 dump、过低=软文）+ 终端输出噪声豁免（重复行在终端输出里是正常的——**规则要按内容类型分桶**，Primus 的"保留代码花括号行/跳过终端标点"即是此意） | datatrove 现成 filter |
| L2 语言/长度 | lid ≥0.65；token 数下限（网页 ~50）与上限（超长走 S8 长上下文通道而非丢弃） | MegaMath |
| L3 领域相关性 | fastText 领域分类器：正类 = 安全工具文档/漏洞通告/渗透 CLI 用法/IDS 规则/加固配置/调试 trace/CTF writeup；负类 = 与工具使用无关的资讯页（**正负类定义照搬 MidTool**，种子用 7B 级 Instruct 模型自动标注 + 人工校验 1–2k 条） | MidTool |
| L4 通用质量 | FineWeb-Edu 式 0–5 打分器（3B 级）：≥3 高质 / 2–3 保留 / <2 默认丢（阈值存配置） | Dolmino 双闸之一 |
| L5 源感知精修（二期） | MIRA 式：按 source_group 聚类 → 教师模型提名维度 → 蒸馏 per-group 评分器（0–10 分 + 理由）；按组设保留阈值 | MIRA |

- **具体考虑**：
  - MidTool/Dolmino 的正负种子构造法可以直接复用：正例 = 高质参考集（如 ATT&CK 文档、优质 writeup、工具手册），负例 = 随机网页池，按分位分桶。
  - "小模型粗筛 + 大模型精修头部"（MegaMath Pro-Max）：L3/L4 用小模型全量跑，L5 与 S7 的教师标注只喂给各 source_group 头部样本，控制成本。
  - PDF 分支更严：OCR 质量分 + ">30% 表格或 >20% 孤立数字直接丢"（Dolmino 经验值）。
  - 每层只打分不硬删，最终"保留决策"由 S8 混合阶段按配置组合分数执行——这使"调阈值不重跑管线"成立（dolma attributes 模式）。

### S4 领域分类 taxonomy

**决策：~10 个内容桶 × {offensive / defensive / neutral} 双轴，multi-label + 置信度；用于配比、课程与安全路由，不做硬过滤。**

- 桶草案：`ctf-writeup`（含 pico/HTB/CTFtime 归档）、`vuln-analysis`（CVE 分析、补丁 diff、advisory）、`exploit-dev`（漏洞利用技术，教学语境）、`malware-re`（恶意软件分析/逆向教学）、`blueteam-ops`（检测规则 YARA/Sigma、SIEM、IR、取证）、`tool-doc`（CLI/工具手册、--help、API 文档）、`sec-code`（安全工具源码、PoC 代码、加固配置）、`policy-compliance`、`sec-news-intel`（低价值，降权）、`forum-qa`。
- 实现：种子 URL/关键词 → 7B 模型 few-shot 标注 → fastText（或 DeBERTa-small）multi-label；低置信度进人工审核队列。
- **具体考虑**：taxonomy 的真正用途有三个——(a) S8 配比按桶控制；(b) 安全路由（`malware-re` 桶过 S6 时提高审查强度）；(c) 评测按桶分层（哪个桶的数据带来哪个桶的能力，用 microanneal 验证）。security news 类页面信息密度低，靠桶标记降权即可，不必硬删。

### S5 去重与污染控制

**去重（按成本升序）**：
1. URL 归一化去重（去 utm/碎片/镜像后缀）；
2. SHA-256 精确去重；
3. 文档级 MinHash：5-gram、hashes_per_bucket=8、9–14 桶（datatrove 三阶段：Signature→Bucket→Filter），Jaccard 0.7–0.8；
4. **代码块级去重**：同一著名 cheat-sheet/nmap 脚本会在几百个页面重复——对规范化后的代码块做 hash 级去重统计，跨页面重复的代码块保留给 top 质量文档（这是安全语料特有的噪声形态）；
5. 图像 pHash/嵌入去重（S2a 已做，此处汇总去冲突）；
6. 环境轨迹按**动作序列** MinHash 近重去重（CWM：Jaccard<0.5 丢弃，防轨迹过拟合）。
顺序：先打分（S3）后去重——高分文档才值得付去重成本（FineWeb 顺序）。

**去污染（安全域比通用域严重得多：CTF writeup 生态就是"复述赛题解法"）**：
- 基准清单入册：cybench、NYU CTF Bench、InterCode-CTF/picoCTF、CyberSecEval 系列、τ²-Bench、BFCL、SWE-bench 仓库黑名单（daVinci 硬编码 12 仓库名的做法）+ 通用集（MMLU/HumanEval/GSM8K）。
- 三层：13-gram 归一化 n-gram 重叠（事实标准）→ MinHash 模糊去重清近似转写 → 嵌入余弦 >0.8–0.85 送 LLM 复核（防释义级泄漏）。
- **CTF 窗口期规则**：进行中/近一年比赛（含 private 泄露风险）的 writeup 全部过滤；历史赛题 writeup 保留（教学价值核心，且基准多为 2021–2024 赛题——需对基准题目标识做定向过滤）。
- 图像分支：截图 OCR 文本并入同一 n-gram 污染库。
- 终解：对外报告用公开基准，**内部选型决策用私有 held-out 新题**（Terminal-Bench 式自建靶场题）。

### S6 安全与合规过滤（双用途）

**决策：文档级三轴 LLM-judge + 确定性工件正则双层；用 FRR 校准防误杀。**

- 确定性层（正则/规则，先跑、便宜）：
  - secrets 扫描：PEM 私钥、AWS AKIA、API key 模式 → `<SECRET>` 哨兵替换（MidTool 实践）；
  - 凭据类列表（password 池、combo list）→ 丢弃；
  - 大块二进制/base64 blob（>N KB 无语义解释）→ 移除保留上下文；
  - 活跃 C2 基础设施（IP/域/DGA 配置）→ 打码。
- 判断层（LLM-judge，三轴，CyberSecEval 2 方法论）：
  1. 意图证据（靶场/教学/研究语境 vs 落地运营）；
  2. ATT&CK 战术映射；
  3. 是否含 operational detail（可直接运行/部署的武器化物）。
- 处置矩阵：
  - **默认保留**（教学/防御/分析语境）：writeup、漏洞机理、补丁 diff、检测规则、加固内容、工具文档、CTI 报告；
  - **移除**：恶意软件样本/源码与免杀、shellcode 库、钓鱼 kit、DoS/僵尸网络工具链、未修补 0day 的可运行 PoC（保留"描述+防护视角"）；
  - **脱敏保留**：exploit-db 类页面以摘要替代完整源码。
- **FRR 校准（关键）**：自建 ~200 条 borderline 良性集（端口扫描教学、取证流程、逆向教程），量化误杀率；参照 CyberSecEval（模型 FRR<15%），**过杀对领域效用是净损失**——Primus 前车之鉴：零过滤 CPT 后 Garak malwaregen 14.3%→29.0%，但另一个极端（SecGPT 式全无过滤）不可接受。
- 图像分支：截图 OCR 文本进同一正则库（凭据与基础设施常出现在截图里）。
- License：代码 permissive 筛选（license_key 随样本走，daVinci 模式）；内容页记录来源与 ToU 状态；审计要求：每条样本可回溯"谁在哪个阶段以什么分数保留了它"。

### S7 agentic 导向重构（本管线区别于通用清洗管线的核心）

**入口门槛：仅 S3 高分（如 L4≥3）且通过 S5/S6 的文档进入。全部增强遵循"grounded + 有界 + 可拒收"。**

#### 7a 文档增强（MidTool 式，主力）
1. 对每篇高分文档生成 **affordance profile**（六字段， MidTool 原型）：可推断工具响应性 / CLI-配置结构证据 / 命令用法 / 工作流结构 / 工具拓扑 / 领域术语。这是"通用网页→agent 教材"的中间表示。
2. **规则式 planner** 决定增强预算（不靠 LLM 自由发挥）：增强量与质量分挂钩、QA 类型有界、**每文档最多一条多轮链**。
3. 增强产物四类（对应安全场景改造）：
   - 工具选择/参数抽取 QA（从文档中的 CLI 用法、配置、报错构造）；
   - **命令-观测对**：把 writeup 中的终端块重建为 `命令 → 预期输出` 对（原生信号，不改内容），序列化直接采用目标 scaffold 的 bash 工具调用 + tool_result 形态（见 7c）；
   - 轨迹链三分族（MidTool 轨迹族 → 安全版）：单命令执行 / 编排链（侦察→利用→驻留→清理）/ **信息缺失追问**（专门训练"参数不全时澄清"）；
   - 状态转移描述（为 7c 供料）。
4. **QC**：解析校验 + 语义校验（工具响应一致性、schema 对齐、必需参数齐全）；不合格带反馈重试一次，再不合格丢弃（MidTool：LLM-judge 拒收率 ~40% 是健康信号，AgentFounder 拒绝 43.5% 把准确率 50%→82%）。
5. 增强比例锚点：MidTool web 36%/52%/11%（源/增强/轨迹化）、code 69% 仅原文、PDF 55% 全链——**代码重清洗轻增强、文档/PDF 重增强**。

#### 7b 代码侧（FIM + 仓库级）
- **FIM 掩码打分移植**：把 FIM 的 Ĥ·Î/(Ĥ+Î) + 难度单边高斯打分族搬到"页面内代码块/安全工具源码"：Ĥ（复杂度：LOC/分支/嵌套，tree-sitter 多语言）× Î（可推断性：引用点密度、签名完整度、文档注释、周边上下文）→ 选高价值掩码目标。掩码单位从"函数体"改为"代码块内完整逻辑单元"（页面无函数结构时退化为块级）。
- LLM 补全 + critic 过滤照搬 FIM 工程：critic JSON（feasibility 先行 + 5 维分 + should_discard 判据写进 prompt）、checkpoint 保留 critic 全文以便免费重滤、**user turn 与训练时字节一致**。
- **仓库级组织**（Qwen3-Coder-Next 结论：优于 file-level）：安全工具仓库按 repo 打包、混用多种序列化格式；PR/commit 数据按 daVinci 渲染模板（`# Repository Context → # Issue → # Edits`，context expansion 20 行）改造成 agentless 编辑语料。编辑块统一用 **str_replace（SEARCH/REPLACE）形态**——与 Claude Code 的 Edit 工具及 Kimi-Dev 的 SEARCH/REPLACE 块同构，daVinci 的 context expansion（20 行，99.8% 唯一化）直接服务于此。
- 配比参考 FIM：single/pair/multi ≈ 80/15/5。

#### 7c 环境轨迹（量小但不可替代，CWM 证据）
- **沙箱状态对任务**（State2State 式）：在自建靶场（DVWA/WebGoat、CTF docker 镜像、shell 沙箱）跑脚本化随机探索（不用 LLM 探索——偏置且贵），存储 (初始快照 → 目标观测) 对；**回放 3 次验证可达性**、单观测重复上限 5、explore-then-operate 20%/80%。验证器 = 归一化精确匹配（零幻觉）。数千级任务即可起效（State2State 用 4k–8k 任务、80 步 RL 就有显著增益）。
- **格式对齐目标 scaffold（已确认：Claude Code / Codex）**：
  - 两个 scaffold 的动作面都是 **bash 执行 + 文件读取 + str_replace 编辑 + 搜索**，表面小且稳定——这大幅简化 7c：只需为这一套工具合成轨迹，再序列化为两种模板（Claude Code 的 XML 式 function call、Codex 的 OpenAI 式 JSON tool call）双格式混训（建议 ~80/20 或 50/50，兼保格式不变性——K-EXAONE 多模板结论）。
  - 参考实现：daVinci-Dev `env_traj_utils/convert_trajectories.py` 已示范"通用 SWE-agent tool_calls → XML function calling（`<function=bash><parameter=command>…`）+ reasoning 包进 `<think>`"的转换，Claude Code 形态可直接借鉴；Codex 形态按 OpenAI tool call JSON 渲染。
  - system prompt 带完整工具 schema（K-EXAONE 工具格式结论），训练时 mask system prompt（Kimi-Dev）；**不要照抄 Anthropic/OpenAI 的私有 system prompt**，用自写兼容版或开源等价物（OpenHands/Mini-SWE-agent 风格），规避版权与泄漏问题。
  - 长 session：Claude Code/Codex 真实会话常超 100K token——观测轮随机 mask ~50%（CWM）+ 长轨迹排入 Stage2，与 S8 阶段设计一致。
- loss 处理见 S8-C。

#### 7d 知识注入（AgentFounder 式，低成本）
- **实体锚定 QA**：实体 = CVE 编号、CWE、ATT&CK 技术号、工具名、漏洞类型；从 CVE 描述/advisory/文档生成事实检索、CVSS 计算、多跳（漏洞→补丁→绕过→检测）四类问题；拒绝采样（LLM-judge 对齐校验）。
- **对比式决策样本**：多候选命令/利用路径选择题 + 正误自判——把"轨迹模仿"升级为"逐步决策"，规避 step-reward 工程（AgentFounder HAS）。
- **克制的推理增强**：文档中插入简短 reasoning（命令前"为什么"），避免长 CoT（OctoThinker 副作用）；采用"思考型预训练"形态时保持 LM 目标全覆盖（Microsoft/Meta 证据：LM 目标下思考增强有效且可数据高效）。

### S8 混合、配比与训练阶段

**混合骨架（首轮 20–50B token 的建议起点，全部数字可被 S10 消融推翻）：**

| 数据族 | 占比 | 说明 |
|---|---|---|
| 领域专项：安全网页（清洗后高质） | ~25% | S3 高分池，全部文本化（截图走 OCR、拓扑图走 VLM 描述） |
| 领域专项：增强产物（QA/命令-观测/轨迹链/FIM） | ~10% | 合成主体，4× 上采样于其原始文档（Kimi-Dev） |
| 领域专项：环境状态对/轨迹 | ~5% | 7c 产物，量小但关键（MidTool 轨迹 9% 槽位） |
| 通用代码/仓库级（含安全工具仓库 + 通用代码） | ~25% | repo 级组织 + 多序列化格式 |
| 通用回放（web/数学/推理/少量指令跟随） | ~27% | CWM 30% 锚点的文本部分；回放内上采样数学与长上下文；指令跟随 ~3% 用于训练早期行为监控（Qwen3-Coder-Next） |
| 通用多模态回放 | 3–5% | 通用（非安全）交错图文；防纯文本 MT 造成视觉通路漂移/遗忘（Aya Vision/CTP 证据；Aya 以文本/多模态检查点融合解决同类问题） |
| 安全图文切片（可选） | 0–2% | 截图类文档"原图+OCR/caption 双信号"，服务"用户贴截图"交互；仅在 S10 实验 2 显示截图探针显著受益时保留 |
| 长文档/跨仓库上下文 | （贯穿） | OctoLong 式依赖扩展为二期选项 |

- QA 类占比 ≤30%（OctoThinker：>30% 平台化）。
- 稀缺高质源按 Dolmino 模式多 epoch（Source% 表示法），封顶 7×。
- **阶段设计**：
  - 上下文目标 ≤32K：单阶段，OctoThinker Stable-then-Decay（200B:20B ≈ 90%:10%，LR 衰减到稳定段 10%）；MidTool 式 1 epoch + WSD 亦可作起点。
  - 上下文目标 ≥128K：两阶段——Stage1（32K，知识+代码+清洗数据，无显式工具格式）→ Stage2（128K，引入工具格式/轨迹/高难数据，长上下文样本占比随窗口同步提高）；依据 Step-DeepResearch、K-EXAONE（Stage2 相对直接 SFT +0.95 互补增益）、PRISM（MT 置于长上下文扩展之后 AIME 9.38→23.59）。
  - **领域数据早引入、高权重**（CMU 可塑性窗口：晚引入 + 高权重显著差于早引入保守混合；渐进加码失败）。
- **Loss mask 规则**（三条，全有出处）：
  1. agentless/PR 配对数据：mask prompt，只监督响应（Kimi-Dev）；
  2. 环境轨迹：只 mask system prompt，action+observation 联合监督；观测轮随机 mask ~50%（CWM，观测多样性低）；重复片段（代码头/配置块）一律 mask（Qwen3-Coder-Next）；
  3. 原生文档（网页/代码/FIM）：全 LM loss，thinking 增强文本同算 loss（Kimi-Dev 对 agentless 数据的对照结论 + 思考型预训练证据）。
- **多模态记账**：多模态份额（通用多模态回放 3–5% + 安全图文切片 0–2%）按图像 token（而非文档数）设额，先用基座 processor 实测图像 token 分布；vision encoder 冻结或低 LR，训练超参以基座建议为准；视觉能力若回退，用 Aya/PRISM 式检查点合并兜底。
- **scaffold 格式记账**：7c 轨迹按 Claude Code/Codex 双模板渲染，两种模板即"格式多样性"载体，不再另设通用工具格式配比。

### S9 元数据、版本化与工程

**工程栈**：
- 骨干：**datatrove**（Python 生态、InferenceRunner/vLLM、MinHash 三阶段、任务级断点）+ 自研抽取器（S1）与图像分支（ray 批处理）。
- 借鉴 dolma 四点：attributes 分离存储（正文不可变、分数旁路）、PII 打标延迟到 mix 替换、per-source 流混合器、resiliparse 对照实现。
- 阶段间 Parquet(Snappy) 交接、schema 集中单文件（daVinci models.go 模式）；图像 webdataset 分片。
- **配置驱动 + 派生路径 + 幂等分片**（FIM 三件套）；确定性 unique_id（样本进入即铸造，中途不改名——FIM 双 id 纪律）；贵步骤（LLM 标注/增强）逐条原子 checkpoint（tmp+rename）并保留完整 LLM 输出（换阈值重滤不再花钱）。
- 每条样本血缘字段：`url, source_group, crawl_ts, license, lang, domain_score, edu_score, dedup_flags, safety_verdict, taxonomy, stage_provenance[]`。完整输出 schema（统一外层 + 四类数据的类型专属字段，含 HF 标杆对照）见**附录 B**。

**LLM 成本量级**（供预算参考）：种子标注 ~10⁵–10⁶ 次小模型调用（vLLM 自托管 7B，成本可忽略）；affordance + 增强用一线模型 API，只喂 S3 头部样本（预估 10⁵–10⁶ 文档 × 每篇 2–5 次调用）——这是管线最大成本项，planner 的"有界增强"就是为此设计。

### S10 评测与消融协议（先于扩量数据生产）

1. **microanneal 选源**（Dolmino）：候选数据桶各用"5B 候选 + 5B web"做 10B 退火快速对比，决定入池与否——把大消融变成小消融。
2. **主消融**（MidTool/daVinci/FIM 共同协议）：同一 base + 同一 SFT/RL 配方，唯一变量是 MT 数据组成；先 4B/8B 级模型。增量消融顺序照 MidTool Table 6：清洗数据 → +原生轨迹 → +增强轨迹 → 完整混合。
3. **评测按能力族分组**（CWM 教训）：
   - agentic 工具/环境：BFCLv3、τ²-Bench、自建靶场 held-out 题（主力决策依据）——**私有题直接跑在与部署一致的 Claude Code/Codex 同构 scaffold 上**（开源承载如 Mini-SWE-agent/OpenHands），避免 scaffold 失配污染消融结论；
   - 安全领域：cybench、NYU CTF（注意去污染后仍作参考）、私有题库；
   - 代码：SWE-bench（Lite/Verified）+ 领域 oracle-patch NLL；
   - 执行/世界模型理解：CruxEval 式（输入/输出预测）；
   - 图文探针（多模态）：自建几百条"终端截图→命令/输出抽取、拓扑图→结构描述"探针集——兼作 S10 实验 1/2 的评测底座，并监控多模态回放/切片对视觉 grounding 的贡献；
   - 通用保持：MMLU、HumanEval、通用 web PPL——**负向检查与正向提升同等重要**。
4. **预算消融**：25%/50%/100% 三个 MT 预算 × 固定后续训练（Kimi-Dev：单调性可外推）；**评测 RL 之后的增益**（OctoThinker：base 平台化后 RL 增益仍随 MT 预算增长）。
5. 迭代回路：消融结果 → 调 S8 配比与 S7 各组件产量 → 重跑 microanneal。短跑结论不采信（CMU：保留效应滞后 ~20k 步）。
6. **图文落点收口实验（v1.2 新增，把"文本为主"决策的不确定性买断）**：
   - 实验 1（零训练，P2 交付）：**OCR 信息保留率审计**——用自建 500–1000 张安全截图评测集分类测量文本化保真率（预期终端/代码截图 >90–95%，拓扑图损失大）；产出兼作图文探针集；
   - 实验 2（一次 ~10B microanneal，P4 执行）：**A = 纯文本安全 MT vs B = 同文本内容 + 截图文档交错**（B 的图像 token 计入预算）；固定 SFT，四组探针（文本 agentic / 截图读图 / 通用视觉回归 / 通用文本回归）。决策规则：A≈B 全线 → 定案纯文本（省成本）；B 仅截图探针显著胜出 → 保留 0–2% 安全图文切片；B 在文本 agentic 上掉点 → 纯文本 + 上调多模态回放。

---

## 4. 实施路线图（建议 4 人月级团队，口径为阶段并行后的净时长）

| 阶段 | 内容 | 交付物 | 时长 |
|---|---|---|---|
| P0 | source_group 清单 + taxonomy 种子 + 管线骨架（config/路径/断点/metadata 规范） | 可运行的空管线 + seed-list | 2 周 |
| P1 | S0/S1/S3 文本分支 MVP（含自定义抽取器 + 领域 fastText v0 + FineWeb-Edu 式打分器） | 首个清洗池（~1B token 级）+ 抽检面板 | 4 周 |
| P2 | S5 去重 + 去污染 + S6 双用途 v1（正则层 + judge 层 + FRR 校准集）+ S2a 图像资产线（过滤/去重/webdataset/OCR-caption 双通道/图像安全审查） | 全量清洗池 v1 + 安全审计报告 + OCR 保留率审计 | 4 周 |
| P3 | S7 全部四个重构组件（含 Claude Code/Codex 双格式轨迹渲染）+ S8 混合器（含图像 token 记账）+ loss mask 实现 | 首版 20B token MT 混合 | 6 周 |
| P4 | S10 消融闭环（microanneal → 4B/8B 消融 → 固定后续训练）+ 图文落点收口实验（OCR 保留率审计复核 + A/B microanneal） | 消融报告 + v2 配比 + 图文落点终审 | 6 周 |

里程碑判定：P1 末尾用抽检面板校准抽取质量（代码块保留率、终端块识别率）；P2 末尾 FRR<15% 且双用途审计通过；P4 末尾形成"哪些数据组件值得扩产"的清单。

---

## 5. 风险与对策

| 风险 | 依据 | 对策 |
|---|---|---|
| 双用途过滤误杀/漏杀 | Primus 零过滤→malwaregen +14.7pp；过杀重创领域效用 | FRR 校准集 + 三轴 judge + 人工审核队列；策略需组织层面签字 |
| CTF 基准污染使消融失真 | writeup 生态天然复述赛题 | 窗口期规则 + 三层去污染 + 私有题库为决策基准 |
| 安全语料总量小，多 epoch 过拟合 | 全量高质仅 1–5B token；Dolmino 上采样封顶 7× | 回放锚定 + 通用混合 30% + 消融看 RL 后增益 |
| 合成增强幻觉 | 增强是最大成本与最大风险项 | grounded（原文锚定）+ planner 有界 + QC 重试一次丢弃 + 拒收率监控（~40%） |
| 轨迹格式过拟合单一 scaffold | Qwen3-Coder-Next 跨 scaffold 迁移有限 | 已确认 Claude Code/Codex 双格式混训，必要时加第三方模板做格式不变性 |
| 图像 token 与存储开销 | 一张 1024² 图 ≈ 数百至上千 token，交错序列膨胀快 | 图像 token 计入配比预算；过滤层剔装饰图；按分辨率分桶调度（CWM 长度分桶思路） |
| 纯文本 MT 致视觉通路漂移 | 多模态基座 + 文本为主 MT 的双向遗忘已知失败模式（Aya Vision/CTP） | 通用多模态回放 3–5% + vision encoder 冻结/低 LR + 必要时 Aya/PRISM 式检查点合并（15/85） |
| scaffold 私有提示词不可照抄 | Claude Code/Codex 官方 system prompt 有版权 | 自写兼容版或开源等价物（OpenHands/Mini-SWE-agent 风格），工具 schema 自建 |
| OCR/图像管线成本失控 | OCR+VLM 是最贵环节 | 先筛后算（S3 分数门控）+ 自建截图评测集选引擎 |
| 长上下文训练不稳定 | 长上下文数据需大 batch（CWM） | 长数据放 Stage2；退化时 15/85 模型合并救援（PRISM） |

## 6. 决策记录与开放问题

1. ~~基座模型与是否多模态~~ **已确认：多模态基座；图文落点 v1.2 定稿为"文本为主、图文为辅"双轨**（安全数据 100% 文本化；通用多模态回放 3–5%；可选安全图文切片 0–2% 由实验定；图像分支作为资产生产线保留交错开关）。决策记录见 6.3。
2. ~~目标 scaffold 与下游 RL 框架~~ **已确认：Claude Code / Codex。** 7c 轨迹与 agentless 编辑语料按这两种格式渲染、双模板混训；私有评测跑同构 scaffold；system prompt 用自写兼容版。
3. **MT token 预算与算力**：20–50B 首轮假设需确认；决定两阶段是否必要。
4. **双用途安全策略的边界**（S6 处置矩阵）：需要法务/安全团队签字，尤其"未修补 0day PoC"与 Exploit-DB 类源的处理。
5. **私有评测题库的投入**：去污染后公开基准不可尽信，自建靶场题库是评测可信度的锚。

### 6.3 决策记录：图文数据"文本为主、图文为辅"（v1.2，2026-09-29）

**问题**：基座为多模态模型，安全网页大量图文交错——mid-training 做交错还是纯文本？

**结论**：安全数据 100% 文本化进 mid-training；图像分支作为"数据资产生产线"建设（交错开关保留）；通用多模态回放 3–5%；可选安全图文切片 0–2% 由实验定。

**依据**：
1. **agentic 证据链全文本**：MidTool（20.3B，连 PDF 都 OCR 文本化）、CWM（bash/编辑文本轨迹）、Kimi-Dev、AgentFounder、State2State、FIM、daVinci——没有任何已发表 agentic MT 收益建立在图像输入上。
2. **scaffold 观测空间**：Claude Code/Codex 的 in-loop 观测是文本 tool_result；图像仅出现在用户主动贴图。唯一 in-loop 吃像素的 computer-use/GUI 家族与目标 scaffold 不同族（P4 原则的推论）。
3. **内容可文本化率高**：安全图像大头是终端/代码截图（本质是文本，OCR 保真率预期 >90–95%）；真正不可文本化的拓扑图在终端 agent 工作流中以命令输出形态出现。Qwen3-Coder-Next Table 1：内容保持型文本化本身就是代码能力杠杆（+8.7~12.3 点）。
4. **成本结构**：图像 token 是文本 3–10 倍；1–5B 高质语料 + 20–50B 预算下，大规模交错会挤占轨迹/FIM/仓库级等已证明杠杆。
5. **交错无害但对症性差**：MINT-1T 在纯文本与多模态基准上同时超过 OBELICS 系、OmniCorpus 消融显示交错维持 MMLU——交错买的是多模态技能，对 agentic 目标不对症。
6. **多模态基座的风险在反向**：纯文本 MT 造成视觉通路漂移/遗忘（Aya Vision 明确记载并以检查点融合解决；CTP 系统研究）；解法是小比例多模态回放 + 冻结/低 LR vision tower + Aya/PRISM 式合并兜底（PRISM 15/85 合并 RULER 6.46→42.16）。

**剩余不确定性由两个实验收口**：OCR 保留率审计（零训练，P2）+ A/B microanneal 四探针（P4，决策规则见 S10 第 6 条）。完整论证存档于 `research/notes/06-图文数据落点决策分析.md`。

---

## 附录 A：调研工作 → 本方案设计点映射

| 调研工作 | 采纳到 |
|---|---|
| MidTool（2608.20314） | S3 fastText 正负类、S7a affordance/planner/QC/轨迹族、S8 轨迹 9% 槽位、S10 Table 6 式消融、secrets 哨兵 |
| CWM（2510.02387） | S8 30/40/30 骨架、观测轮 50% mask、轨迹 MinHash、长上下文大 batch、能力族评测 |
| Kimi-Dev（2509.23045） | agentless/PR 配对数据、4× 上采样、loss mask 双轨、预算单调性 |
| Qwen3-Coder-Next（2603.00729） | repo 级组织、内容保持型改写、跨 scaffold 迁移限制、自然数据主体、重复片段 mask |
| FIM（2607.12463） | S7b 打分族与全部工程（checkpoint/critic schema/id 纪律/license 透传） |
| daVinci-Dev（2601.18418） | context expansion 编辑语料、代理缓存、四级廉价过滤、license 字段 |
| AgentFounder（2509.13310） | 实体锚定 QA、对比式决策合成、拒绝采样强度、前 15B 收益规律 |
| State2State（2608.04934） | 7c 状态对任务、回放验证、多样性配额 |
| Dolmino（2501.00656/2512.13961） | 双分类器闸、microanneal、Source% 上采样封顶、PDF 丢弃规则 |
| MegaMath | LID 0.65、小模型粗筛+大模型精修范式 |
| MIRA（2605.30288） | S3-L5 源感知评分器架构 |
| OBELICS/MINT-1T | S2a 全部图像过滤规则、文档级过滤主张、PDF 单列 |
| Primus（2502.11191） | 逐源阈值、dom-to-semantic-markdown、双用途教训（malwaregen 恶化数据） |
| CyberSecEval 2 | S6 三轴 judge、FRR 校准、ATT&CK 映射 |
| CMU（2510.14865） | 通用混合必要性、早引入高权重、消融步数警告 |
| PRISM（2603.17074） | 领域数据放 MT 的判据、MT 置于长上下文扩展之后、15/85 合并救援 |
| OctoThinker（2506.20512） | Stable-then-Decay、QA ≤30%、长 CoT 副作用与渐进 max-length |
| Step-DeepResearch / K-EXAONE 2.0 | 两阶段课程（无工具→工具）、长上下文占比随窗口提高、多模板工具格式 |
| SmolLM3 mid.yaml | 训练配置参照（32K/packing/lr 2e-5/低峰 LR 10%） |
| Aya Vision / CTP / OmniCorpus / MINT-1T | S2a 图文落点决策、多模态回放与视觉通路保护、交错对文本中性证据（见 6.3 与 notes/06） |

## 附录 B：HF 标杆样本库与输出 schema 标准（v1.2）

> 样本实体与数据卡在 `research/reference/`（samples/ 16 个文件 175 条真实条目；cards/ 13 份数据卡；fetch_samples.py 可重跑）。本附录承载其结论，供远端开发直接查阅；该目录 README 与本附录内容同源。

### B.1 样本清单与我方场景的对应关系

我方爬取数据四类：①漏洞分析/逆向 writeup、②渗透测试报告、③CTF writeup、④安全工具使用教程。

| 参考数据集 | 状态 | 参考价值 | 样本文件 |
|---|---|---|---|
| Dolmino / dolma3（OLMo 2/3 MT 数据） | 开放 | **最接近①③④的网页文本化形态**：CC 高质网页、olmOCR 文本化 PDF、StackEdu-FIM、wiki RCQA | `dolmino-cc-hq-software-dev / olmocr-pdf-software / stackedu-fim-{shell,python} / wiki-rcqa` |
| FIM-Midtraining-400K（TIGER-Lab） | 开放 | 代码 MT 样本格式标杆：掩码上下文→推理→实现 + 全程 metadata | `fim-midtraining-400K` |
| AgentTrove（169.7 万条 agent 轨迹） | 开放 | 轨迹 schema 标杆：conversations + 验证器三元组 + 溯源四元组 | `agenttrove` |
| Smoltalk2-Mid（SmolLM3 MT 子集） | 开放 | 推理 MT 的 chat 形态（`<think>`）+ source 字段 | `smoltalk2-mid-{nemotron,openthoughts3}` |
| MegaMath-Web-Pro-Max | 开放 | **网页→训练文本形态标杆**：LLM 改写后干净正文 + 双打分 + 来源元数据 | `megamath-web-pro-max` |
| Nemotron-Pretraining-Specialized | 开放 | 专项合成数据形态：自带 docstring/doctest 的"概念教学文档"式代码 | `nemotron-specialized-code-concepts` |
| OctoLong cross-repo-code-sample | 开放 | 依赖扩展样本 + 扩展过程量化指标 | `octolong-cross-repo` |
| pentest-agent-dataset-chatml | 开放 | ②渗透测试内容形态（CVE 问答型） | `pentest-agent-chatml` |
| bug-bounty-pentest-en | 开放 | ②渗透测试报告结构化形态（多 type 行 + 利用/修复/赏金字段） | `bug-bounty-pentest-en` |
| win-exe-malware-analysis | 开放 | ①逆向分析结构化形态：沙箱报告（进程树/签名/MITRE TTPs），**无二进制** | `win-exe-malware-analysis` |
| Trendyol-Cybersecurity-Instruct | 开放 | 安全 instruction 形态参照 | `trendyol-cybersec-instruct` |
| MidTool-Mix（20.3B agentic MT） | **gated** | 最对口的 agentic MT；数据卡已存，schema 见 notes/03 | — |
| daVinci-Dev | **gated** | 代码 agent MT；数据卡已存 | — |
| Primus-Seed（Trend Micro 安全 CPT 种子） | **gated** | **最接近我方场景的安全域原始语料**；数据卡已存 | — |

> gated 解锁：`huggingface-cli login` → 数据集页接受条款（MidTool/daVinci 需机构信息）→ 重跑 `fetch_samples.py`。MidTool 两个 fastText 分类器同为 gated（README 已存）。

### B.2 关键观察

- **Dolmino（S1–S3 输出形态基准）**：W3C-IDO 风格 `{text, id, metadata, added, created, source, version}`；正文不可变、分数全进 metadata；`int_score`（FineWeb-Edu 式 0–5）+ `score`（fastText）**双打分并存**；license/repo/path/uri 每条可回溯。CC 高质网页分片为扁平纯文本（保内容轻格式）；olmOCR 分片证明双栏 PDF 线性化即可验收；StackEdu-FIM 分片存原始代码文档，FIM 掩码训练时才套用。
- **MegaMath-Web-Pro-Max（改写后网页标杆）**：text 为 LLM 改写后的干净正文（结构化步骤、无广告残留），`url+timestamp+lang+lang_score+双分数` 必存——④工具教程、①writeup 的精修层参照。
- **FIM-400K（代码 MT 样本模板）**：`{messages:[user 固定模板+掩码文件, assistant: ###Reasoning + ###Implementation 代码围栏], metadata, fim_split}`——S7b 逐字段对齐，训练文本与发送 prompt 字节一致。
- **AgentTrove（轨迹 schema 标杆）**：验证器三元组 `verifier_output/ground_truth/judgment` + 溯源四元组 `original_source/original_teacher/run_id/trial_name`；system prompt 显式规定结构化响应格式（terminal-bench 风格 JSON 批次）——结构可参照，**响应格式须替换为我方 Claude Code/Codex 双模板**。
- **安全域 instruction 类（形态参考，不作质量标杆）**：bug-bounty 单文件多 type 行（methodology/checklist/technique/qa，各带专属字段）是②的结构化参照；win-exe 沙箱报告（behavior/signatures/ttps）示范"分析报告不含任何二进制工件"（对应 S6 处置矩阵）。这批均为 SFT 风格，归入 S7d 或后训练参考，不进 MT 主池。

### B.3 跨标杆共性纪律（我方输出硬要求）

1. 正文不可变 + 分数旁路（Dolmino 模式）；2. 每条样本可回溯（来源/时间/license 三件套全程携带）；3. 通用质量分与领域分分开存；4. 合成/增强样本必须带溯源与验证（teacher、模板版本、verifier、judgment）；5. 训练形态对齐目标 scaffold（轨迹用双模板）；6. 文本化产出"线性化但结构可读"即可，不追求还原排版。

### B.4 我方四类数据的输出 schema 建议（对齐 S7/S9）

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

| 类型 | text 形态 | 额外 metadata | 参照标杆 |
|---|---|---|---|
| ①漏洞/逆向 writeup | markdown：标题/环境/步骤/终端块/结论；截图插 `[图: caption]`+OCR 文本 | `cve_ids[]`, `attack_tactics[]`, `tool_names[]`, `artifact_scan` | dolmino-cc-hq + win-exe-malware |
| ②渗透测试报告 | 结构化段落：scope→findings→步骤→影响→修复；避免可运营工件 | `report_sections{}`, `severity`, `scope` | bug-bounty 字段集 |
| ③CTF writeup | 挑战名/分类/难度→思路→命令-观测序列→flag 处理（赛题 flag 打码） | `ctf_event`, `year`(窗口期规则), `category`, `scaffold_format` | pentest-agent + AgentTrove |
| ④工具教程 | 命令/参数/输出/常见错误；终端块可独立成命令-观测对 | `tool_name`, `tool_version`, `affordance_profile` | megamath 形态 + MidTool affordance |
| 代码 FIM（S7b） | messages[user 模板+掩码上下文, assistant Reasoning+Implementation] | `fim_split`, `repo_id`, `file_path`, `license` | FIM-400K 逐字段对齐 |
| 轨迹（S7c） | Claude Code/Codex 双模板 conversations | `scaffold_format`, `verifier_output`, `ground_truth`, `judgment`, `run_id` | AgentTrove 元数据模板 |
| 状态对（S7c） | (初始快照→目标观测) + 归一化匹配规则 | `env`, `replay_verified(3x)`, `diversity_key` | State2State（notes/03） |
| 知识 QA（S7d） | 实体锚定 QA；拒绝采样留存 | `entity`, `qa_style`, `reject_rate` | AgentFounder FAS（notes/03） |

> 落地顺序：P0 用本附录统一外层冻结 `metadata` 必填集（id/url/source_group/license/quality/safety），P1 起每类 text 形态以对应标杆样本逐条对照验收。

## 附录 C：调研报告索引

- `research/notes/01-工程骨干与质量过滤.md` — datatrove/dolma 核验、过滤栈、Dolmino/MegaMath/MIRA 细节、SmolLM3 配置
- `research/notes/02-图文交错与安全领域特殊性.md` — OBELICS/MINT-1T/OCR、数据源许可证清单、双用途草案、去污染
- `research/notes/03-MidTool与agentic合成路线.md` — MidTool/AgentFounder/State2State 方法细节
- `research/notes/04-FIM与daVinci-Dev代码级分析.md` — 两仓库代码级核验
- `research/notes/05-工业报告配比与阶段设计.md` — CWM/Kimi-Dev/Qwen3-Coder-Next 等八篇设计规则
- `research/notes/06-图文数据落点决策分析.md` — "文本为主 vs 交错"决策分析（v1.2 决策依据，含收口实验协议）
- `research/reference/` — **HF 标杆样本库**：13 个数据集的真实样本条目（samples/）+ 数据卡（cards/）+ 我方四类数据的输出 schema 建议（README.md）；gated 的 MidTool-Mix/daVinci-Dev/Primus-Seed 已存数据卡，登录并接受条款后可用 fetch_samples.py 补齐样本
- `research/repos/` — FIM-Midtraining、daVinci-Dev、datatrove、dolma、MegaMath（浅克隆）
