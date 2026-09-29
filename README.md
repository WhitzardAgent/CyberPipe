# CyberPipe

面向**网络安全领域**的 mid-training 数据清洗与重构管线，目标是提升下游 **agentic 能力**（Claude Code / Codex 类 scaffold 的工具使用、多步操作、环境交互）。

处理对象：安全网页数据（代码、图文交错两类），具体包括漏洞分析/逆向 writeup、渗透测试报告、CTF writeup、安全工具使用教程等。

## 仓库地图

| 路径 | 内容 |
|---|---|
| [PLAN.md](PLAN.md) | **管线实施方案 v1.2**（主文档）：总体架构、S0–S10 各设计点、混合配比与训练阶段、评测消融协议、路线图、决策记录 |
| [research/notes/](research/notes/) | 六份调研报告：工程骨干与质量过滤、图文交错与安全域特殊性、MidTool/AgentFounder/State2State、FIM 与 daVinci-Dev 代码级分析、工业报告配比与阶段设计、图文落点决策分析 |
| [research/reference/](research/reference/) | **HF 标杆样本库**：13 个数据集的官方数据卡（cards/）、16 个开放数据集的真实样本条目（samples/，共 175 条）、可重跑抓取脚本，以及我方四类数据（writeup/渗透报告/CTF writeup/工具教程）的输出 schema 建议 |
| [research/repos/](research/repos/) | 参考代码库的本地 clone（**不入库**，见 .gitignore；恢复方式见下） |

## 已定决策

1. 基座为**多模态模型**；图文数据落点为"**文本为主、图文为辅**"双轨（安全数据 100% 文本化，图像分支作为可翻转的数据资产生产线，另设多模态回放保护视觉通路）。
2. 目标 agent scaffold = **Claude Code / Codex**，轨迹与编辑语料按这两种格式渲染、双模板混训。
3. 纯清洗不产生 agentic 收益：管线 = 清洗骨干 + agentic 导向重构层（affordance 增强 / FIM / 状态对轨迹 / 知识注入），轨迹类数据预留 ~10% 槽位。

## 参考代码库恢复

```bash
mkdir -p research/repos && cd research/repos
git clone --depth 1 https://github.com/TIGER-AI-Lab/FIM-Midtraining
git clone --depth 1 https://github.com/GAIR-NLP/daVinci-Dev
git clone --depth 1 https://github.com/huggingface/datatrove
git clone --depth 1 https://github.com/allenai/dolma
```

## 关键依据

调研覆盖 25+ 项公开工作（OLMo/Dolmino、SmolLM3、MidTool、FIM-Midtraining、daVinci-Dev、CWM、Kimi-Dev、AgentFounder、Qwen3-Coder-Next、PRISM、MIRA、State2State、OctoThinker/OctoLong、Primus 等），全部结论标注原始出处，见 research/notes/。
