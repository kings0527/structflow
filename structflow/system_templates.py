"""System Type Templates — 系统结构模板库.

V2.2 Core Insight:
  不可能维护5000个行业模板，但可以维护20个底层系统模板。
  LLM是推理引擎，不是知识来源。
  真正决定质量的是模板库，不是模型本身。

Architecture: 4层
  1. System Ontology (系统本体) — 系统类型识别
  2. Variable Library (变量库) — 每个系统类型的标准变量
  3. Search Strategy (搜索策略) — 每个变量的搜索关键词和数据源
  4. Evidence Weight (证据权重) — 数据源可信度排序

Usage:
  L0 输出 system_type → 匹配模板 → 模板提供:
    - 默认变量 (SV/FV/CV/LV) 作为 LLM 的脚手架
    - 搜索关键词 (中英文) 用于 data_collector
    - 数据源权重 用于结果排序
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SystemTemplate:
    """一个系统类型的模板：变量 + 搜索策略 + 证据权重."""

    name: str  # 模板名称
    system_types: list[str]  # 匹配的 system_type 关键词
    aliases: list[str]  # 中文别名

    # 变量库 — LLM 的脚手架 (不是硬约束，LLM可以修改/扩展)
    variables: dict[str, list[str]]  # {"SV": [...], "FV": [...], "CV": [...], "LV": [...]}

    # 搜索策略 — 每个变量类型的关键词 (中英文)
    search_keywords: dict[str, dict[str, list[str]]]  # {"SV": {"zh": [...], "en": [...]}}

    # 证据权重库 — 数据源可信度
    evidence_weights: dict[str, float] = field(default_factory=dict)

    # 搜索后缀 — 该系统类型常用的搜索上下文
    search_context: dict[str, list[str]] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# 10 个核心系统模板
# ──────────────────────────────────────────────────────────────────────

TEMPLATES: list[SystemTemplate] = [

    # 1. 资源系统 — 黄金/铜/铁/锂/稀土
    SystemTemplate(
        name="resource_system",
        system_types=["resource", "mining", "commodity", "资源", "矿产"],
        aliases=["资源系统", "矿产行业", "大宗商品"],
        variables={
            "SV": ["储量", "品位", "产能", "库存", "成本曲线", "开采年限"],
            "FV": ["产量", "出口量", "进口量", "价格", "资本开支"],
            "CV": ["开采许可", "环保法规", "出口关税", "资源税", "补贴政策"],
            "LV": ["市场风险偏好", "地缘政治预期", "库存周期预期", "美元走势预期"],
        },
        search_keywords={
            "SV": {"zh": ["储量", "产能", "库存"], "en": ["reserves", "capacity", "inventory"]},
            "FV": {"zh": ["产量", "价格", "出口"], "en": ["production", "price", "exports"]},
            "CV": {"zh": ["开采许可", "环保", "关税"], "en": ["mining permit", "environmental", "tariff"]},
            "LV": {"zh": ["风险偏好", "地缘政治"], "en": ["risk appetite", "geopolitical"]},
        },
        evidence_weights={
            "企业财报": 0.95, "行业协会": 0.90, "海关数据": 0.85,
            "监管文件": 0.90, "研究机构": 0.75, "新闻": 0.30, "自媒体": 0.10,
        },
        search_context={
            "initial": ["market overview supply demand", "cost curve production", "reserves inventory"],
            "l0": ["failure mode supply disruption", "cost structure"],
            "l2": ["driver supply demand forecast"],
        },
    ),

    # 2. 能源系统 — 石油/天然气/煤炭/光伏/风电
    SystemTemplate(
        name="energy_system",
        system_types=["energy", "oil", "gas", "petroleum", "power", "能源", "石油", "电力"],
        aliases=["能源系统", "石化和天然气", "电力行业"],
        variables={
            "SV": ["探明储量", "炼化产能", "发电装机量", "库存", "管网长度"],
            "FV": ["日产量", "发电量", "消费量", "价格", "资本开支"],
            "CV": ["碳税", "排放标准", "补贴政策", "准入许可", "价格管制"],
            "LV": ["能源安全预期", "转型信心", "地缘政治风险溢价", "天气预期"],
        },
        search_keywords={
            "SV": {"zh": ["产能", "装机量", "库存"], "en": ["capacity", "installed capacity", "inventory"]},
            "FV": {"zh": ["产量", "消费量", "价格"], "en": ["production", "consumption", "price"]},
            "CV": {"zh": ["碳税", "排放", "补贴"], "en": ["carbon tax", "emissions", "subsidy"]},
            "LV": {"zh": ["能源安全", "地缘政治"], "en": ["energy security", "geopolitical"]},
        },
        evidence_weights={
            "企业财报": 0.95, "行业协会": 0.90, "政府统计": 0.90,
            "监管文件": 0.90, "研究机构": 0.75, "新闻": 0.30,
        },
    ),

    # 3. 制造系统 — 化工/钢铁/半导体/汽车
    SystemTemplate(
        name="manufacturing_system",
        system_types=["manufacturing", "chemical", "steel", "semiconductor", "automotive", "制造", "化工", "钢铁", "半导体"],
        aliases=["制造系统", "工业企业", "重化工"],
        variables={
            "SV": ["产能", "装置利用率", "库存", "资本存量", "技术专利数"],
            "FV": ["产量", "出货量", "订单量", "价格", "资本开支"],
            "CV": ["环保法规", "关税", "利率", "产业政策", "安全标准"],
            "LV": ["行业景气预期", "技术创新扩散", "库存周期预期", "贸易摩擦预期"],
        },
        search_keywords={
            "SV": {"zh": ["产能", "开工率", "库存"], "en": ["capacity", "utilization rate", "inventory"]},
            "FV": {"zh": ["产量", "订单", "价格"], "en": ["production", "orders", "price"]},
            "CV": {"zh": ["环保", "关税", "利率"], "en": ["environmental regulation", "tariff", "interest rate"]},
            "LV": {"zh": ["景气度", "技术趋势"], "en": ["business cycle", "technology trend"]},
        },
        evidence_weights={
            "企业财报": 0.95, "行业协会": 0.90, "海关数据": 0.85,
            "监管文件": 0.90, "电话会纪要": 0.80, "新闻": 0.30,
        },
        search_context={
            "initial": ["industry overview capacity utilization", "supply demand balance", "cost structure"],
            "l0": ["failure mode capacity utilization", "supply disruption"],
            "l2": ["driver capacity demand forecast"],
        },
    ),

    # 4. 平台系统 — 电商/社交/外卖/搜索
    SystemTemplate(
        name="platform_system",
        system_types=["platform", "e-commerce", "social media", "internet", "平台", "电商", "互联网"],
        aliases=["平台系统", "互联网平台", "数字经济"],
        variables={
            "SV": ["月活用户", "商家数", "基础设施规模", "数据资产", "市场份额"],
            "FV": ["GMV", "收入", "广告收入", "支付流水", "研发投入"],
            "CV": ["反垄断监管", "数据隐私法", "税收政策", "准入门槛", "跨境规则"],
            "LV": ["用户信任度", "网络效应强度", "创新预期", "监管风险预期"],
        },
        search_keywords={
            "SV": {"zh": ["用户数", "商家数", "市场份额"], "en": ["users", "merchants", "market share"]},
            "FV": {"zh": ["GMV", "收入", "广告"], "en": ["GMV", "revenue", "advertising"]},
            "CV": {"zh": ["反垄断", "数据隐私", "税收"], "en": ["antitrust", "data privacy", "tax"]},
            "LV": {"zh": ["用户信任", "网络效应"], "en": ["user trust", "network effects"]},
        },
        evidence_weights={
            "企业财报": 0.95, "行业报告": 0.85, "应用商店数据": 0.80,
            "监管文件": 0.90, "新闻": 0.30, "自媒体": 0.10,
        },
    ),

    # 5. 信用系统 — 银行/保险/金融
    SystemTemplate(
        name="credit_system",
        system_types=["banking", "credit", "insurance", "financial", "银行", "保险", "金融"],
        aliases=["信用系统", "金融机构", "信贷"],
        variables={
            "SV": ["总资产", "贷款余额", "存款余额", "资本充足率", "不良贷款率"],
            "FV": ["净息差", "新增贷款", "保费收入", "利润", "拨备"],
            "CV": ["利率政策", "存准率", "资本要求", "监管强度", "牌照"],
            "LV": ["信用信心", "风险偏好", "违约预期", "流动性预期"],
        },
        search_keywords={
            "SV": {"zh": ["资产", "贷款", "存款"], "en": ["assets", "loans", "deposits"]},
            "FV": {"zh": ["净息差", "利润", "保费"], "en": ["net interest margin", "profit", "premium"]},
            "CV": {"zh": ["利率", "存准率", "资本充足"], "en": ["interest rate", "reserve ratio", "capital adequacy"]},
            "LV": {"zh": ["信用信心", "违约预期"], "en": ["credit confidence", "default expectation"]},
        },
        evidence_weights={
            "企业财报": 0.95, "央行数据": 0.95, "监管文件": 0.90,
            "行业协会": 0.85, "评级机构": 0.80, "新闻": 0.30,
        },
    ),

    # 6. 软件/IT系统 — SaaS/云/网络安全
    SystemTemplate(
        name="software_system",
        system_types=["software", "saas", "cloud", "cybersecurity", "IT", "软件", "云计算"],
        aliases=["软件系统", "科技企业", "SaaS"],
        variables={
            "SV": ["客户数", "ARR", "研发人员", "技术栈", "市场份额"],
            "FV": ["新增订阅", "收入", "流失率", "研发投入", "并购支出"],
            "CV": ["数据合规", "出口管制", "知识产权", "云监管", "反垄断"],
            "LV": ["技术趋势预期", "迁移意愿", "安全信心", "估值溢价预期"],
        },
        search_keywords={
            "SV": {"zh": ["客户数", "ARR", "市场份额"], "en": ["customers", "ARR", "market share"]},
            "FV": {"zh": ["订阅收入", "流失率"], "en": ["subscription revenue", "churn rate"]},
            "CV": {"zh": ["数据合规", "出口管制"], "en": ["data compliance", "export control"]},
            "LV": {"zh": ["技术趋势", "迁移意愿"], "en": ["technology trend", "migration intent"]},
        },
        evidence_weights={
            "企业财报": 0.95, "行业报告": 0.85, "技术分析": 0.75,
            "监管文件": 0.90, "新闻": 0.30,
        },
    ),

    # 7. 基础设施系统 — 电信/公用事业/交通
    SystemTemplate(
        name="infrastructure_system",
        system_types=["infrastructure", "telecom", "utility", "transport", "基础设施", "电信", "公用事业", "交通"],
        aliases=["基础设施系统", "公用事业", "运输"],
        variables={
            "SV": ["管网长度", "装机容量", "线路里程", "用户连接数", "资产净值"],
            "FV": ["收入", "客货运量", "维护支出", "资本开支", "能源消耗"],
            "CV": ["价格管制", "准入许可", "安全标准", "环保要求", "补贴"],
            "LV": ["需求增长预期", "政策稳定性", "技术替代风险", "利率敏感度"],
        },
        search_keywords={
            "SV": {"zh": ["管网", "装机", "用户数"], "en": ["network", "capacity", "users"]},
            "FV": {"zh": ["收入", "运量"], "en": ["revenue", "traffic volume"]},
            "CV": {"zh": ["价格管制", "准入"], "en": ["price regulation", "licensing"]},
            "LV": {"zh": ["需求预期", "政策稳定"], "en": ["demand outlook", "policy stability"]},
        },
        evidence_weights={
            "企业财报": 0.95, "政府统计": 0.90, "行业协会": 0.85,
            "监管文件": 0.90, "新闻": 0.30,
        },
    ),

    # 8. 消费品牌系统 — 食品/饮料/服装/化妆品
    SystemTemplate(
        name="consumer_brand_system",
        system_types=["consumer", "food", "beverage", "apparel", "cosmetics", "消费", "食品", "饮料", "服装", "化妆品"],
        aliases=["消费品牌系统", "快消品", "品牌消费"],
        variables={
            "SV": ["品牌资产", "渠道数", "产能", "库存", "用户基数"],
            "FV": ["销售额", "销量", "广告投入", "新品收入", "渠道扩张"],
            "CV": ["消费税", "食品安全标准", "广告法规", "进口关税", "价格管控"],
            "LV": ["品牌忠诚度", "消费信心", "潮流趋势", "健康意识"],
        },
        search_keywords={
            "SV": {"zh": ["品牌", "渠道", "库存"], "en": ["brand", "channels", "inventory"]},
            "FV": {"zh": ["销售额", "销量", "广告"], "en": ["sales", "volume", "advertising"]},
            "CV": {"zh": ["消费税", "食品安全"], "en": ["consumption tax", "food safety"]},
            "LV": {"zh": ["品牌忠诚", "消费信心"], "en": ["brand loyalty", "consumer confidence"]},
        },
        evidence_weights={
            "企业财报": 0.95, "市场调研": 0.85, "行业协会": 0.85,
            "电商数据": 0.80, "新闻": 0.30, "自媒体": 0.10,
        },
    ),

    # 9. 房地产系统
    SystemTemplate(
        name="real_estate_system",
        system_types=["real estate", "property", "construction", "房地产", "地产", "建筑"],
        aliases=["房地产系统", "地产", "建筑"],
        variables={
            "SV": ["土地储备", "在建面积", "竣工面积", "库存", "杠杆率"],
            "FV": ["销售面积", "销售金额", "新开工", "土地购置", "融资流入"],
            "CV": ["限购政策", "房贷利率", "土地供应", "预售制度", "房企融资政策"],
            "LV": ["房价预期", "购房信心", "政策预期", "违约风险预期"],
        },
        search_keywords={
            "SV": {"zh": ["土地储备", "在建", "库存"], "en": ["land reserve", "construction", "inventory"]},
            "FV": {"zh": ["销售面积", "新开工"], "en": ["sales area", "new starts"]},
            "CV": {"zh": ["限购", "房贷利率"], "en": ["purchase restriction", "mortgage rate"]},
            "LV": {"zh": ["房价预期", "购房信心"], "en": ["price expectation", "buyer confidence"]},
        },
        evidence_weights={
            "企业财报": 0.95, "政府统计": 0.90, "行业协会": 0.85,
            "监管文件": 0.90, "新闻": 0.30,
        },
    ),

    # 10. 加密/区块链系统 — ETH/BTC/DeFi
    SystemTemplate(
        name="crypto_system",
        system_types=["crypto", "blockchain", "defi", "ethereum", "bitcoin", "加密", "区块链", "以太坊", "比特币"],
        aliases=["加密系统", "区块链", "Web3", "去中心化", "分布式结算", "智能合约"],
        variables={
            "SV": ["总供应量", "质押量", "DeFi TVL", "L2 TVL", "验证者数量", "代币化资产规模"],
            "FV": ["日交易量", "活跃地址数", "手续费燃烧", "ETF净流入", "稳定币发行量"],
            "CV": ["监管框架", "稳定币规则", "ETF审批", "税收政策", "合规要求"],
            "LV": ["市场情绪", "风险偏好", "叙事强度", "机构信心", "流动性预期"],
        },
        search_keywords={
            "SV": {"zh": ["质押量", "TVL", "供应量"], "en": ["staking", "TVL", "supply"]},
            "FV": {"zh": ["交易量", "活跃地址", "ETF流入"], "en": ["transaction volume", "active addresses", "ETF inflows"]},
            "CV": {"zh": ["监管", "ETF审批", "稳定币"], "en": ["regulation", "ETF approval", "stablecoin"]},
            "LV": {"zh": ["市场情绪", "叙事", "机构信心"], "en": ["market sentiment", "narrative", "institutional confidence"]},
        },
        evidence_weights={
            "链上数据": 0.95, "企业财报": 0.90, "监管文件": 0.90,
            "行业报告": 0.80, "新闻": 0.30, "自媒体": 0.10,
        },
        search_context={
            "initial": ["market overview TVL", "staking yield supply", "tokenization RWA"],
            "l0": ["failure mode security consensus", "value capture"],
            "l2": ["driver ETF flows staking regulation"],
        },
    ),
]


# ──────────────────────────────────────────────────────────────────────
# 模板匹配
# ──────────────────────────────────────────────────────────────────────

def match_template(system_type: str) -> SystemTemplate | None:
    """根据 L0 输出的 system_type 匹配最合适的模板.

    匹配逻辑:
    1. 精确匹配 system_types 列表
    2. 模糊匹配 (关键词包含)
    3. 返回 None 表示无匹配 (LLM 自行生成变量)

    Args:
        system_type: L0 输出的 system_type 字段 (可能是中文/英文/混合)

    Returns:
        匹配的 SystemTemplate 或 None
    """
    if not system_type:
        return None

    st_lower = system_type.lower()

    # 1. 精确匹配
    for tpl in TEMPLATES:
        for keyword in tpl.system_types:
            if keyword.lower() == st_lower:
                return tpl

    # 2. 模糊匹配 — 多关键词计分: 匹配关键词数 × 平均长度
    best_match = None
    best_score = 0
    for tpl in TEMPLATES:
        match_count = 0
        total_len = 0
        for keyword in tpl.system_types + tpl.aliases:
            if keyword.lower() in st_lower:
                match_count += 1
                total_len += len(keyword)
        if match_count > 0:
            # Score = match_count × average_keyword_length
            avg_len = total_len / match_count
            score = match_count * avg_len
            if score > best_score:
                best_score = score
                best_match = tpl

    return best_match if best_score >= 2 else None


def get_template_variables(template: SystemTemplate | None) -> dict[str, list[str]] | None:
    """获取模板的默认变量 (供 L1 作为脚手架使用)."""
    if not template:
        return None
    return template.variables


def get_template_search_keywords(template: SystemTemplate | None, var_type: str, lang: str = "en") -> list[str]:
    """获取模板中某变量类型的搜索关键词.

    Args:
        template: 系统模板
        var_type: "SV" | "FV" | "CV" | "LV"
        lang: "en" for Tavily, "zh" for AnySearch

    Returns:
        搜索关键词列表 (如 ["reserves", "capacity", "inventory"])
    """
    if not template:
        return []
    var_keywords = template.search_keywords.get(var_type, {})
    return var_keywords.get(lang, [])


def get_template_search_context(template: SystemTemplate | None, phase: str = "initial") -> list[str]:
    """获取模板的搜索上下文后缀.

    Args:
        template: 系统模板
        phase: "initial" | "l0" | "l2"

    Returns:
        搜索后缀列表 (如 ["market overview supply demand", "cost curve"])
    """
    if not template:
        return []
    return template.search_context.get(phase, [])


def get_evidence_weight(source_type: str, template: SystemTemplate | None = None) -> float:
    """获取数据源的证据权重.

    Args:
        source_type: 数据源类型 (如 "企业财报", "新闻")
        template: 系统模板 (可选，提供特定权重)

    Returns:
        权重 0-1 (默认 0.5)
    """
    if template and source_type in template.evidence_weights:
        return template.evidence_weights[source_type]
    # 默认权重
    defaults = {
        "企业财报": 0.95, "央行数据": 0.95, "政府统计": 0.90,
        "行业协会": 0.85, "监管文件": 0.90, "海关数据": 0.85,
        "链上数据": 0.95, "市场调研": 0.80, "评级机构": 0.80,
        "研究机构": 0.75, "电话会纪要": 0.80, "电商数据": 0.80,
        "应用商店数据": 0.80, "新闻": 0.30, "自媒体": 0.10,
    }
    return defaults.get(source_type, 0.5)
