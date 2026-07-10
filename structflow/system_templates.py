"""System Type Templates — 方法论模板库.

核心理念：
  模板不提供变量列表（直接抄），而是提供方法论（怎么思考）。
  LLM用方法论去推导具体变量，而非复制模板变量。
  模板告诉LLM：结构、层级、方法论，让其进行延伸泛化拓展。

Usage:
  L0 输出 system_type → match_template() → 模板提供:
    - 结构描述 (这个系统类型的特征)
    - 方法论 (如何识别SV/FV/CV/LV)
    - 搜索关键词 (用于data_collector)
    - 证据权重 (数据源可信度)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SystemTemplate:
    """一个系统类型的方法论模板."""

    name: str
    system_types: list[str]
    aliases: list[str]

    # 方法论 — 告诉LLM怎么思考
    structure: str  # 系统的结构特征 (1-2句，描述这个系统类型的核心特征)
    methodology: dict[str, str]  # {"SV": "问什么+看什么模式", "FV": "...", ...}

    # 搜索策略
    search_keywords: dict[str, dict[str, list[str]]]
    evidence_weights: dict[str, float] = field(default_factory=dict)
    search_context: dict[str, list[str]] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# 10 个核心系统模板
# ──────────────────────────────────────────────────────────────────────

TEMPLATES: list[SystemTemplate] = [

    # 1. 资源系统
    SystemTemplate(
        name="resource_system",
        system_types=["resource", "mining", "commodity", "资源", "矿产"],
        aliases=["资源系统", "矿产行业", "大宗商品"],
        structure=(
            "资源系统的核心是：不可再生的物理储量通过开采转化为可交易商品。"
            "供给端受地质禀赋和开采成本约束，需求端受工业用途和避险需求驱动。"
            "价格由边际成本曲线和库存周期共同决定。"
        ),
        methodology={
            "SV": "问：什么物理量在系统中累积或存留？看模式：地下储量、地面库存、已建设产能、成本曲线位置。关键是找'存量'——随时间变化缓慢的量。",
            "FV": "问：什么在系统中流动和变化？看模式：开采产量、贸易进出口、市场价格、资本勘探支出。关键是找'流量'——单位时间内的变化率。",
            "CV": "问：什么规则控制着开采和贸易？看模式：采矿许可、环保法规、出口关税、资源税。关键是找'杠杆点'——可以直接干预的变量。",
            "LV": "问：什么不可观测但决定价格？看模式：市场风险偏好、地缘政治预期、库存周期预期、美元走势预期。关键是找'心理量'——无法直接测量但影响行为的因素。",
        },
        search_keywords={
            "SV": {"zh": ["储量", "产能", "库存"], "en": ["reserves", "capacity", "inventory"]},
            "FV": {"zh": ["产量", "价格", "出口"], "en": ["production", "price", "exports"]},
            "CV": {"zh": ["开采许可", "环保", "关税"], "en": ["mining permit", "environmental", "tariff"]},
            "LV": {"zh": ["风险偏好", "地缘政治"], "en": ["risk appetite", "geopolitical"]},
        },
        evidence_weights={"企业财报": 0.95, "行业协会": 0.90, "海关数据": 0.85, "监管文件": 0.90, "研究机构": 0.75, "新闻": 0.30, "自媒体": 0.10},
    ),

    # 2. 能源系统
    SystemTemplate(
        name="energy_system",
        system_types=["energy", "oil", "gas", "petroleum", "power", "能源", "石油", "电力"],
        aliases=["能源系统", "石化和天然气", "电力行业"],
        structure=(
            "能源系统的核心是：将一次能源（化石/可再生）转化为可用能源产品。"
            "供给端受资源禀赋和基础设施约束，需求端受经济活动和天气驱动。"
            "碳约束正在重塑成本曲线和竞争格局。"
        ),
        methodology={
            "SV": "问：什么能源基础设施和储量在累积？看模式：探明储量、炼化产能、发电装机量、管网长度、战略储备。",
            "FV": "问：什么能源在流动？看模式：日产量、发电量、消费量、价格、能源贸易流量。",
            "CV": "问：什么规则控制能源生产和消费？看模式：碳税、排放标准、补贴政策、价格管制、准入许可。",
            "LV": "问：什么预期影响能源决策？看模式：能源安全预期、转型信心、地缘政治风险溢价、天气预期。",
        },
        search_keywords={
            "SV": {"zh": ["产能", "装机量", "库存"], "en": ["capacity", "installed capacity", "inventory"]},
            "FV": {"zh": ["产量", "消费量", "价格"], "en": ["production", "consumption", "price"]},
            "CV": {"zh": ["碳税", "排放", "补贴"], "en": ["carbon tax", "emissions", "subsidy"]},
            "LV": {"zh": ["能源安全", "地缘政治"], "en": ["energy security", "geopolitical"]},
        },
        evidence_weights={"企业财报": 0.95, "行业协会": 0.90, "政府统计": 0.90, "监管文件": 0.90, "研究机构": 0.75, "新闻": 0.30},
    ),

    # 3. 制造系统
    SystemTemplate(
        name="manufacturing_system",
        system_types=["manufacturing", "chemical", "steel", "semiconductor", "automotive", "制造", "化工", "钢铁", "半导体"],
        aliases=["制造系统", "工业企业", "重化工"],
        structure=(
            "制造系统的核心是：通过资本密集的生产装置将原料转化为工业品。"
            "产能利用率和库存周期决定盈利能力，技术路线和规模效应决定成本曲线。"
            "产能扩张有滞后性，导致周期性供需错配。"
        ),
        methodology={
            "SV": "问：什么生产能力在累积？看模式：装置产能、开工率、库存水平、资本存量、技术专利。关键是找'固定投入'——已经花掉的钱形成的产能。",
            "FV": "问：什么在生产和流动？看模式：产量、出货量、订单量、产品价格、资本开支。关键是找'经营流量'——每季度变化的量。",
            "CV": "问：什么规则约束生产？看模式：环保法规、关税壁垒、利率水平、产业政策、安全标准。关键是找'外部约束'。",
            "LV": "问：什么预期影响生产决策？看模式：行业景气预期、技术创新扩散速度、库存周期预期、贸易摩擦预期。关键是找'决策心理'。",
        },
        search_keywords={
            "SV": {"zh": ["产能", "开工率", "库存"], "en": ["capacity", "utilization rate", "inventory"]},
            "FV": {"zh": ["产量", "订单", "价格"], "en": ["production", "orders", "price"]},
            "CV": {"zh": ["环保", "关税", "利率"], "en": ["environmental regulation", "tariff", "interest rate"]},
            "LV": {"zh": ["景气度", "技术趋势"], "en": ["business cycle", "technology trend"]},
        },
        evidence_weights={"企业财报": 0.95, "行业协会": 0.90, "海关数据": 0.85, "监管文件": 0.90, "电话会纪要": 0.80, "新闻": 0.30},
        search_context={
            "initial": ["industry overview capacity utilization", "supply demand balance", "cost structure"],
            "l0": ["failure mode capacity utilization", "supply disruption"],
            "l2": ["driver capacity demand forecast"],
        },
    ),

    # 4. 平台系统
    SystemTemplate(
        name="platform_system",
        system_types=["platform", "e-commerce", "social media", "internet", "平台", "电商", "互联网"],
        aliases=["平台系统", "互联网平台", "数字经济"],
        structure=(
            "平台系统的核心是：双边市场通过网络效应连接用户和商家。"
            "数据资产和网络效应形成正反馈飞轮，用户基数和ARPU决定收入。"
            "监管和反垄断是最大的外部约束。"
        ),
        methodology={
            "SV": "问：什么用户和基础设施在累积？看模式：月活用户、商家数、数据资产、基础设施规模、市场份额。关键是找'网络存量'——越多越好用的量。",
            "FV": "问：什么在平台上流动？看模式：GMV、广告收入、支付流水、研发投入、内容产出。关键是找'变现流量'。",
            "CV": "问：什么规则约束平台运营？看模式：反垄断监管、数据隐私法、税收政策、跨境规则。关键是找'合规约束'。",
            "LV": "问：什么影响用户和商家信心？看模式：用户信任度、网络效应强度、创新预期、监管风险预期。关键是找'信任心理'。",
        },
        search_keywords={
            "SV": {"zh": ["用户数", "商家数", "市场份额"], "en": ["users", "merchants", "market share"]},
            "FV": {"zh": ["GMV", "收入", "广告"], "en": ["GMV", "revenue", "advertising"]},
            "CV": {"zh": ["反垄断", "数据隐私", "税收"], "en": ["antitrust", "data privacy", "tax"]},
            "LV": {"zh": ["用户信任", "网络效应"], "en": ["user trust", "network effects"]},
        },
        evidence_weights={"企业财报": 0.95, "行业报告": 0.85, "应用商店数据": 0.80, "监管文件": 0.90, "新闻": 0.30, "自媒体": 0.10},
    ),

    # 5. 信用系统
    SystemTemplate(
        name="credit_system",
        system_types=["banking", "credit", "insurance", "financial", "银行", "保险", "金融"],
        aliases=["信用系统", "金融机构", "信贷"],
        structure=(
            "信用系统的核心是：通过杠杆将存款转化为贷款，赚取息差。"
            "信用扩张和收缩具有周期性，坏账率和资本充足率决定生存能力。"
            "监管和利率政策是最强的外部控制变量。"
        ),
        methodology={
            "SV": "问：什么资产负债在累积？看模式：总资产、贷款余额、存款余额、资本充足率、不良贷款率。关键是找'存量健康度'。",
            "FV": "问：什么信用在扩张收缩？看模式：净息差、新增贷款、保费收入、利润、拨备计提。关键是找'盈利流量'。",
            "CV": "问：什么规则约束信用扩张？看模式：利率政策、存准率、资本要求、监管强度、牌照。关键是找'监管杠杆'。",
            "LV": "问：什么信心影响信用行为？看模式：信用信心、风险偏好、违约预期、流动性预期。关键是找'信用心理'。",
        },
        search_keywords={
            "SV": {"zh": ["资产", "贷款", "存款"], "en": ["assets", "loans", "deposits"]},
            "FV": {"zh": ["净息差", "利润", "保费"], "en": ["net interest margin", "profit", "premium"]},
            "CV": {"zh": ["利率", "存准率", "资本充足"], "en": ["interest rate", "reserve ratio", "capital adequacy"]},
            "LV": {"zh": ["信用信心", "违约预期"], "en": ["credit confidence", "default expectation"]},
        },
        evidence_weights={"企业财报": 0.95, "央行数据": 0.95, "监管文件": 0.90, "行业协会": 0.85, "评级机构": 0.80, "新闻": 0.30},
    ),

    # 6. 软件系统
    SystemTemplate(
        name="software_system",
        system_types=["software", "saas", "cloud", "cybersecurity", "IT", "软件", "云计算"],
        aliases=["软件系统", "科技企业", "SaaS"],
        structure=(
            "软件系统的核心是：通过订阅模式将研发投入转化为经常性收入。"
            "客户留存和ARR增长决定估值，技术迁移成本形成粘性。"
            "数据合规和出口管制是关键外部约束。"
        ),
        methodology={
            "SV": "问：什么客户和技术在累积？看模式：客户数、ARR、研发人员、技术栈、市场份额。关键是找'订阅存量'。",
            "FV": "问：什么收入在流动？看模式：新增订阅、收入、流失率、研发投入、并购支出。关键是找'增长流量'。",
            "CV": "问：什么规则约束软件运营？看模式：数据合规、出口管制、知识产权、云监管。关键是找'合规约束'。",
            "LV": "问：什么预期影响技术决策？看模式：技术趋势预期、迁移意愿、安全信心、估值溢价预期。关键是找'技术心理'。",
        },
        search_keywords={
            "SV": {"zh": ["客户数", "ARR", "市场份额"], "en": ["customers", "ARR", "market share"]},
            "FV": {"zh": ["订阅收入", "流失率"], "en": ["subscription revenue", "churn rate"]},
            "CV": {"zh": ["数据合规", "出口管制"], "en": ["data compliance", "export control"]},
            "LV": {"zh": ["技术趋势", "迁移意愿"], "en": ["technology trend", "migration intent"]},
        },
        evidence_weights={"企业财报": 0.95, "行业报告": 0.85, "技术分析": 0.75, "监管文件": 0.90, "新闻": 0.30},
    ),

    # 7. 基础设施系统
    SystemTemplate(
        name="infrastructure_system",
        system_types=["infrastructure", "telecom", "utility", "transport", "基础设施", "电信", "公用事业", "交通"],
        aliases=["基础设施系统", "公用事业", "运输"],
        structure=(
            "基础设施系统的核心是：通过重资产网络提供垄断性公共服务。"
            "价格管制和准入许可决定收入上限，需求增长和政策稳定性决定长期价值。"
            "利率敏感度高，是典型的长久期资产。"
        ),
        methodology={
            "SV": "问：什么物理网络在累积？看模式：管网长度、装机容量、线路里程、用户连接数、资产净值。关键是找'网络存量'。",
            "FV": "问：什么服务在流动？看模式：收入、客货运量、维护支出、资本开支、能源消耗。关键是找'运营流量'。",
            "CV": "问：什么规则约束定价和准入？看模式：价格管制、准入许可、安全标准、环保要求。关键是找'监管约束'。",
            "LV": "问：什么预期影响长期投资？看模式：需求增长预期、政策稳定性、技术替代风险、利率敏感度。关键是找'长期预期'。",
        },
        search_keywords={
            "SV": {"zh": ["管网", "装机", "用户数"], "en": ["network", "capacity", "users"]},
            "FV": {"zh": ["收入", "运量"], "en": ["revenue", "traffic volume"]},
            "CV": {"zh": ["价格管制", "准入"], "en": ["price regulation", "licensing"]},
            "LV": {"zh": ["需求预期", "政策稳定"], "en": ["demand outlook", "policy stability"]},
        },
        evidence_weights={"企业财报": 0.95, "政府统计": 0.90, "行业协会": 0.85, "监管文件": 0.90, "新闻": 0.30},
    ),

    # 8. 消费品牌系统
    SystemTemplate(
        name="consumer_brand_system",
        system_types=["consumer", "food", "beverage", "apparel", "cosmetics", "消费", "食品", "饮料", "服装", "化妆品"],
        aliases=["消费品牌系统", "快消品", "品牌消费"],
        structure=(
            "消费品牌系统的核心是：通过品牌溢价和渠道渗透将产品差异化定价。"
            "品牌资产和用户忠诚度是护城河，消费信心和渠道效率决定增长。"
            "食品安全和广告法规是关键约束。"
        ),
        methodology={
            "SV": "问：什么品牌和渠道在累积？看模式：品牌资产、渠道数、产能、库存、用户基数。关键是找'品牌存量'。",
            "FV": "问：什么在销售和变化？看模式：销售额、销量、广告投入、新品收入、渠道扩张。关键是找'变现流量'。",
            "CV": "问：什么规则约束品牌运营？看模式：消费税、食品安全标准、广告法规、进口关税。关键是找'合规约束'。",
            "LV": "问：什么影响消费决策？看模式：品牌忠诚度、消费信心、潮流趋势、健康意识。关键是找'消费心理'。",
        },
        search_keywords={
            "SV": {"zh": ["品牌", "渠道", "库存"], "en": ["brand", "channels", "inventory"]},
            "FV": {"zh": ["销售额", "销量", "广告"], "en": ["sales", "volume", "advertising"]},
            "CV": {"zh": ["消费税", "食品安全"], "en": ["consumption tax", "food safety"]},
            "LV": {"zh": ["品牌忠诚", "消费信心"], "en": ["brand loyalty", "consumer confidence"]},
        },
        evidence_weights={"企业财报": 0.95, "市场调研": 0.85, "行业协会": 0.85, "电商数据": 0.80, "新闻": 0.30, "自媒体": 0.10},
    ),

    # 9. 房地产系统
    SystemTemplate(
        name="real_estate_system",
        system_types=["real estate", "property", "construction", "房地产", "地产", "建筑"],
        aliases=["房地产系统", "地产", "建筑"],
        structure=(
            "房地产系统的核心是：通过土地和杠杆将资金转化为可售物业。"
            "库存周期和杠杆率决定生存能力，政策周期决定价格方向。"
            "预售制度和融资政策是最强的外部控制。"
        ),
        methodology={
            "SV": "问：什么土地和物业在累积？看模式：土地储备、在建面积、竣工面积、库存、杠杆率。关键是找'存量健康度'。",
            "FV": "问：什么在销售和建设？看模式：销售面积、销售金额、新开工、土地购置、融资流入。关键是找'经营流量'。",
            "CV": "问：什么政策控制房地产？看模式：限购政策、房贷利率、土地供应、预售制度、融资政策。关键是找'政策杠杆'。",
            "LV": "问：什么预期影响购房决策？看模式：房价预期、购房信心、政策预期、违约风险预期。关键是找'购房心理'。",
        },
        search_keywords={
            "SV": {"zh": ["土地储备", "在建", "库存"], "en": ["land reserve", "construction", "inventory"]},
            "FV": {"zh": ["销售面积", "新开工"], "en": ["sales area", "new starts"]},
            "CV": {"zh": ["限购", "房贷利率"], "en": ["purchase restriction", "mortgage rate"]},
            "LV": {"zh": ["房价预期", "购房信心"], "en": ["price expectation", "buyer confidence"]},
        },
        evidence_weights={"企业财报": 0.95, "政府统计": 0.90, "行业协会": 0.85, "监管文件": 0.90, "新闻": 0.30},
    ),

    # 10. 加密/区块链系统
    SystemTemplate(
        name="crypto_system",
        system_types=["crypto", "blockchain", "defi", "ethereum", "bitcoin", "加密", "区块链", "以太坊", "比特币"],
        aliases=["加密系统", "区块链", "Web3", "去中心化", "分布式结算", "智能合约"],
        structure=(
            "加密系统的核心是：通过共识机制和密码学实现去中心化价值转移。"
            "代币经济模型决定激励结构，链上活动和机构资金流入决定价值捕获。"
            "监管框架和叙事周期是最强的外部变量。"
        ),
        methodology={
            "SV": "问：什么链上资产在累积？看模式：总供应量、质押量、DeFi TVL、L2 TVL、验证者数量、代币化资产规模。关键是找'链上存量'——区块上记录的累积量。",
            "FV": "问：什么在链上流动？看模式：日交易量、活跃地址数、手续费燃烧、ETF净流入、稳定币发行量。关键是找'链上活跃度'——网络使用率的流量指标。",
            "CV": "问：什么规则约束加密系统？看模式：监管框架、稳定币规则、ETF审批、税收政策、合规要求。关键是找'监管约束'——传统金融对加密的约束。",
            "LV": "问：什么叙事影响市场？看模式：市场情绪、风险偏好、叙事强度、机构信心、流动性预期。关键是找'叙事心理'——驱动资金流入流出的信念。",
        },
        search_keywords={
            "SV": {"zh": ["质押量", "TVL", "供应量"], "en": ["staking", "TVL", "supply"]},
            "FV": {"zh": ["交易量", "活跃地址", "ETF流入"], "en": ["transaction volume", "active addresses", "ETF inflows"]},
            "CV": {"zh": ["监管", "ETF审批", "稳定币"], "en": ["regulation", "ETF approval", "stablecoin"]},
            "LV": {"zh": ["市场情绪", "叙事", "机构信心"], "en": ["market sentiment", "narrative", "institutional confidence"]},
        },
        evidence_weights={"链上数据": 0.95, "企业财报": 0.90, "监管文件": 0.90, "行业报告": 0.80, "新闻": 0.30, "自媒体": 0.10},
        search_context={
            "initial": ["market overview TVL", "staking yield supply", "tokenization RWA"],
            "l0": ["failure mode security consensus", "value capture"],
            "l2": ["driver ETF flows staking regulation"],
        },
    ),
]


# ──────────────────────────────────────────────────────────────────────
# 模板匹配与获取
# ──────────────────────────────────────────────────────────────────────

def _keyword_matches(keyword: str, text: str) -> bool:
    """Match short ASCII keywords as tokens, not word fragments."""
    normalized_keyword = " ".join(keyword.lower().split())
    normalized_text = " ".join(text.lower().split())
    if not normalized_keyword:
        return False
    if re.fullmatch(r"[a-z0-9+#.-]{1,3}", normalized_keyword):
        pattern = (
            rf"(?<![a-z0-9]){re.escape(normalized_keyword)}"
            r"(?![a-z0-9])"
        )
        return re.search(pattern, normalized_text) is not None
    return normalized_keyword in normalized_text


def match_template(system_type: str) -> SystemTemplate | None:
    """根据 L0 输出的 system_type 匹配模板."""
    if not system_type:
        return None
    st_lower = system_type.lower()

    # 1. 精确匹配
    for tpl in TEMPLATES:
        for keyword in tpl.system_types:
            if keyword.lower() == st_lower:
                return tpl

    # 2. 多关键词计分
    best_match, best_score = None, 0
    for tpl in TEMPLATES:
        match_count, total_len = 0, 0
        for keyword in tpl.system_types + tpl.aliases:
            if _keyword_matches(keyword, st_lower):
                match_count += 1
                total_len += len(keyword)
        if match_count > 0:
            score = match_count * (total_len / match_count)
            if score > best_score:
                best_score, best_match = score, tpl
    return best_match if best_score >= 2 else None


def get_template_methodology(template: SystemTemplate | None) -> dict[str, str] | None:
    """获取模板的方法论 (结构描述 + 每个变量类型的思考方法).

    供 L1 使用 — 告诉 LLM 怎么思考，而非直接给变量。
    """
    if not template:
        return None
    return {
        "structure": template.structure,
        "SV": template.methodology.get("SV", ""),
        "FV": template.methodology.get("FV", ""),
        "CV": template.methodology.get("CV", ""),
        "LV": template.methodology.get("LV", ""),
    }


def get_template_search_keywords(template: SystemTemplate | None, var_type: str, lang: str = "en") -> list[str]:
    """获取模板中某变量类型的搜索关键词."""
    if not template:
        return []
    return template.search_keywords.get(var_type, {}).get(lang, [])


def get_template_search_context(template: SystemTemplate | None, phase: str = "initial") -> list[str]:
    """获取模板的搜索上下文后缀."""
    if not template:
        return []
    return template.search_context.get(phase, [])


def get_evidence_weight(source_type: str, template: SystemTemplate | None = None) -> float:
    """获取数据源的证据权重."""
    if template and source_type in template.evidence_weights:
        return template.evidence_weights[source_type]
    defaults = {
        "企业财报": 0.95, "央行数据": 0.95, "政府统计": 0.90,
        "行业协会": 0.85, "监管文件": 0.90, "海关数据": 0.85,
        "链上数据": 0.95, "市场调研": 0.80, "评级机构": 0.80,
        "研究机构": 0.75, "电话会纪要": 0.80, "电商数据": 0.80,
        "应用商店数据": 0.80, "新闻": 0.30, "自媒体": 0.10,
    }
    return defaults.get(source_type, 0.5)
