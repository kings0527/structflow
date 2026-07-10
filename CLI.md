# StructFlow CLI 使用指南

## 概述

StructFlow 是一个行业扫描 Agent，通过结构化分析识别行业的权力-流动-风险结构。

**核心能力**：
- 识别行业结构（Structure Mapping）
- 识别权力与风险分布（Power & Risk Mapping）
- 输出可比较的评分向量（Comparable Score Vector）

**数据来源**：
- Tavily Web Search API（实时行业数据）
- LLM 预训练知识（结构分析框架）

---

## 安装

```bash
# 克隆仓库
git clone git@github.com:kings0527/structflow.git
cd structflow

# 安装依赖
pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API keys
```

---

## 配置

### .env 文件

```bash
# LLM 配置
LLM_MODEL=deepseek-v4-flash
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com
LLM_ENABLE_THINKING=true
LLM_REASONING_EFFORT=high

# Tavily 搜索 API
TAVILY_API_KEY=tvly-xxx

# 数据采集
ENABLE_WEB_SEARCH=true
SEARCH_MAX_RESULTS=10
SEARCH_DEPTH=advanced
```

### 环境变量优先级

CLI 参数 > .env 文件 > 默认值

---

## 基本用法

### 最简命令

```bash
# 使用 .env 配置，启用 web 搜索
structflow "semiconductor" --search
```

### 完整参数

```bash
structflow "semiconductor" \
  --region "China" \
  --horizon mid \
  --peers "TSMC" "Samsung" "Intel" \
  --output markdown \
  --model deepseek-v4-flash \
  --api-key sk-xxx \
  --base-url https://api.deepseek.com \
  --thinking \
  --reasoning-effort high \
  --search \
  --tavily-key tvly-xxx
```

---

## 参数详解

### 必需参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `industry` | 行业名称 | `"semiconductor"`, `"cloud computing"` |

### 可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--region` | `global` | 地理区域，如 `"China"`, `"US"` |
| `--horizon` | `mid` | 时间范围：`short` / `mid` / `long` |
| `--peers` | `[]` | 对标公司列表，如 `--peers AWS Azure GCP` |
| `--output` | `markdown` | 输出格式：`terminal` / `markdown` / `json` |

### LLM 配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model` | `.env` 中配置 | LLM 模型名称 |
| `--api-key` | `.env` 中配置 | LLM API Key |
| `--base-url` | `.env` 中配置 | LLM API Base URL |
| `--no-thinking` | `false` | 关闭默认启用的 DeepSeek thinking 模式 |
| `--reasoning-effort` | `high` | 推理强度：`low` / `medium` / `high` |

### 数据采集

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--no-search` | `false` | 关闭默认启用的 Web 搜索 |
| `--tavily-key` | `.env` 中配置 | Tavily API Key |

---

## 使用示例

### 1. 基本行业扫描（启用搜索）

```bash
structflow "EV battery" --search
```

**输出**：终端彩色面板，包含 7 个分析章节 + Gate 验证结果

### 2. 带对标公司的深度分析

```bash
structflow "cloud computing" \
  --peers "AWS" "Azure" "GCP" "Alibaba Cloud" \
  --region "Global" \
  --horizon long \
  --search
```

**输出**：包含公司评分排名和结构健康度对比

### 3. 输出为 Markdown 文件

```bash
structflow "semiconductor" \
  --region "China" \
  --search \
  --output markdown > semiconductor_report.md
```

**输出**：标准 Markdown 格式，可直接用于文档

### 4. 输出为 JSON（供其他 Agent 使用）

```bash
structflow "fintech" \
  --peers "Stripe" "Square" "PayPal" \
  --search \
  --output json > fintech_scan.json
```

**输出**：结构化 JSON，包含所有分析结果

### 5. 使用 OpenAI GPT-4o

```bash
structflow "biotech" \
  --model gpt-4o \
  --api-key sk-xxx \
  --base-url https://api.openai.com/v1 \
  --search
```

### 6. 禁用 Web 搜索（仅 LLM 知识）

```bash
structflow "semiconductor" --no-search
```

**适用场景**：快速原型验证、无 Tavily API Key 时

---

## 输出格式

### Terminal（默认）

彩色终端输出，包含：
- 实时进度显示（L0 → L1 → L2 → L3）
- Gate 验证结果（✓ / ✗）
- 最终报告面板

### Markdown

标准 Markdown 格式，包含 7 个章节：

```markdown
# Industry Scan Report: semiconductor (China)

## 1. Structure Map
## 2. Flow Map
## 3. Power Map
## 4. Risk Map
## 5. Score Vector
## 6. Structural Phase
## 7. Key Fragilities

## Gate Validation
```

### JSON

完整结构化数据，包含：
- `industry_definition`: L0 行业定义
- `structure`: L1 结构拆解
- `power_map`: 权力矩阵
- `flow_analysis`: L2 流动风险分析
- `industry_structure_score`: L3 行业评分
- `companies_ranked`: 公司排名
- `structural_phase`: 行业阶段
- `gate_validation`: Gate 验证结果
- `key_fragilities`: 关键脆弱性

---

## 架构说明

### 四层分析流程

```
Data Collection (Tavily)
    ↓
L0: Industry Definition (行业本体定义)
    ↓
L1: Structure Decomposition (四角色拆解 + 权力矩阵)
    ↓
L2: Flow & Risk Analysis (三流追踪：钱/信息/风险)
    ↓
L3: Scoring & Ranking (S向量评分 + 公司排序)
    ↓
Gate Validation (5个强制验证门)
    ↓
Output (标准化报告)
```

### 5 个 Hard Gates

| Gate | 检查内容 | 失败后果 |
|------|----------|----------|
| Gate 1 | 是否识别控制权（4角色 + 5权力维度） | 输出无效 |
| Gate 2 | 是否识别风险归属（利润/风险分离） | 输出无效 |
| Gate 3 | 是否识别信息不对称（谁先知道） | 输出无效 |
| Gate 4 | 是否检测隐藏流（补贴/政策依赖） | 输出无效 |
| Gate 5 | 是否可横向比较（评分向量完整） | 输出无效 |

---

## 供其他 Agent 调用

### Python API

```python
from structflow.agent import run_scan
from structflow.models import ScanInput, TimeHorizon
from structflow.llm_client import LLMClient

# 配置 LLM
client = LLMClient(
    model="deepseek-v4-flash",
    api_key="sk-xxx",
    base_url="https://api.deepseek.com",
    enable_thinking=True,
    reasoning_effort="high",
)

# 执行扫描
scan_input = ScanInput(
    industry="semiconductor",
    region="China",
    time_horizon=TimeHorizon.MID,
    peer_set=["TSMC", "Samsung"],
)

output = run_scan(
    scan_input,
    client,
    enable_search=True,
    tavily_key="tvly-xxx",
)

# 使用结果
print(output.industry_definition.core_need)
print(output.structural_phase.stage.value)
for company in output.companies_ranked:
    print(f"{company.name}: {company.structural_health}")
```

### JSON 输出集成

```bash
# 其他 Agent 调用
structflow "semiconductor" --output json | jq '.companies_ranked[0].name'
```

---

## 故障排除

### 1. Tavily API Key 无效

```
Error: Tavily API key not configured
```

**解决**：在 `.env` 中设置 `TAVILY_API_KEY` 或使用 `--tavily-key` 参数

### 2. LLM API 调用失败

```
Error: 401 Unauthorized
```

**解决**：检查 `LLM_API_KEY` 和 `LLM_BASE_URL` 是否正确

### 3. DeepSeek thinking 模式超时

DeepSeek thinking 模式响应较慢（单次调用 30-60s），完整扫描需要 2-4 分钟。

**解决**：耐心等待，或禁用 thinking 模式：

```bash
structflow "semiconductor" --search  # 不添加 --thinking
```

### 4. Gate 验证失败

```
⚠ Gate validation failed: Gate1_ControlIdentified
```

**解决**：
- 启用 `--search` 获取更多真实数据
- 检查行业名称是否过于宽泛
- 添加 `--peers` 指定具体公司

---

## 性能优化

### 快速模式（无搜索 + 无 thinking）

```bash
structflow "semiconductor" --no-search
```

**耗时**：~30s

### 标准模式（搜索 + thinking）

```bash
structflow "semiconductor" --search --thinking
```

**耗时**：~3-4 分钟

### 深度模式（搜索 + thinking + 多公司）

```bash
structflow "semiconductor" \
  --peers "TSMC" "Samsung" "Intel" "GlobalFoundries" \
  --search \
  --thinking \
  --reasoning-effort high
```

**耗时**：~5-6 分钟

---

## 许可证

MIT License
