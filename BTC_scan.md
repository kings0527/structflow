# Industry Scan Report: BTC

**Time Horizon**: mid
**Core Need**: 比特币满足了一个不可审查、数字稀缺、全球可转移的价值存储需求，作为去中心化的储备资产和长期通胀对冲工具。
**Substitution Risk**: 0.3 | **Demand Stability**: 0.55 | **Narrative Dependency**: 0.45

---
## 1. Structure Map

### Producer
- **Entities**: MARA Holdings, Riot Platforms, Cipher Mining, F2Pool, Antpool, 其他大型矿池（如Foundry USA, Braiins）
- **Description**: 通过工作量证明创建新区块并获得区块奖励与交易费，是比特币的原始供应方。矿池聚合算力，降低个体矿工方差，并一定程度影响交易确认顺序。

### Payer
- **Entities**: Strategy (MSTR), Metaplanet, Twenty One Capital, 个人投资者, 机构投资者, ETF（如IBIT、FBTC）, 企业金库（如特斯拉、Block）
- **Description**: 购买比特币作为价值储存、投资资产或资产负债表工具。ETF和机构通过受监管渠道获取敞口，形成长期持有需求。

### Mediator
- **Entities**: Binance, Coinbase, Kraken, Bitfinex, Gemini, OKEx, KuCoin, Grayscale, Bitwise, 稳定币发行商（如Tether、Circle）, 托管人（如Coinbase Custody、BitGo）
- **Description**: 交易所提供流动性、价格发现和交易撮合；ETP/信托提供合规投资通道；稳定币发行商提供链上美元计价结算工具，降低交易摩擦；托管人保障资产安全，降低对手方风险。

### Controller
- **Entities**: 美国SEC, 美国CFTC, 白宫（通过行政命令设立战略比特币储备）, 美国国会（CLARITY法案、GENIUS法案）, FASB（会计准则制定）, Basel委员会（银行资本要求）, Bitcoin Core开发者（协议更新）, 矿工（通过共识规则，如segwit激活）
- **Description**: 监管机构制定合规框架、市场结构规则及税收政策；法案明确资产分类与披露要求；开发者定义协议标准（BIPs）；矿工通过运行代码影响网络升级；会计准则影响企业资产负债表处理。

### Supplier
- **Entities**: Bitmain, MicroBT, Canaan, 三星（半导体）, 台积电（芯片代工）, 电力公司（如德克萨斯电网ERCOT）
- **Description**: 提供ASIC矿机、芯片及电力基础设施。矿机供应商控制硬件性能和供应量，电力供应商影响矿工成本结构。

### Complementor
- **Entities**: 闪电网络（Lightning Labs）, Layer 2扩展方案, 合规审计机构（如Chainalysis、TRM Labs）, 评级机构（如Moody's对标普）
- **Description**: 提供增强比特币可用性、合规性和信任的补充服务。审计链上交易、提供合规工具；评级机构评估发行方信用。

---

## 2. Flow Map

### Cash Flow Chain
- **个人投资者/机构/ETF/企业金库** (Producer (资本提供者)): 提供法币资金购买比特币，形成初始需求
- **Binance/Coinbase/Kraken等交易所** (Mediator (交易中介)): 撮合买卖，收取手续费，提供流动性
- **MARA Holdings/Riot Platforms等矿工及OTC卖家** (Producer (比特币生产者)): 通过挖矿或场外交易出售比特币，回收法币
- **电力公司（如ERCOT）** (Supplier (能源供应商)): 向矿工提供电力，收取电费
- **Bitmain/MicroBT等矿机厂商** (Supplier (硬件供应商)): 销售ASIC矿机，回收法币
- **Foundry USA/AntPool等矿池** (Mediator (算力聚合)): 聚合算力，分配区块奖励，收取手续费
- **美国国税局/地方政府** (Controller (税收征收)): 对资本利得、矿工收入征税
- **衍生品市场（CME/期权/期货）** (Mediator (风险转移)): 提供杠杆、对冲工具，资金流通过保证金和清算所
- **稳定币发行商（Tether/Circle）** (Mediator (结算中介)): 发行USDT/USDC，用于交易所结算和跨境流动

### Value Capture Points
- **交易所（Binance/Coinbase）** (Mediator): 通过交易手续费、上币费、做市服务费，年收入数十亿
- **低成本工业矿工（Riot等）** (Producer): 以$0.03/kWh电价挖矿，生产成本$25k-$46k/BTC，售价$71k获利$25k-$46k
- **比特币财库公司（Strategy/MSTR）** (Producer/Controller): 发行股票/债券融资购买比特币，股价溢价（mNAV>1）捕获额外价值
- **矿机供应商（Bitmain）** (Supplier): 销售ASIC矿机，毛利率30%-50%，控制硬件供应
- **ETP发行商（Grayscale/Bitwise）** (Mediator): 收取管理费（0.2%-1.5%），管理资产超$140B
- **矿池（Foundry/AntPool）** (Mediator): 收取矿池手续费（约2%-4%），控制算力分配
- **托管商（Coinbase Prime/BitGo）** (Mediator): 收取托管费，提供保险和合规服务
- **衍生品清算所（如CME）** (Mediator): 收取清算费、保证金利息，交易量巨大

### Information Asymmetry
- **矿工（MARA/Riot）** (Producer): 最先知道自身算力、电力成本、产量，以及网络难度、交易池状态
- **矿池（Foundry/AntPool）** (Mediator): 最先知道全网算力分布、交易打包情况、Stratum V2协议变更
- **交易所（Coinbase/Binance）** (Mediator): 掌握订单簿深度、交易量、用户KYC数据、链下流动性，可预判短期价格
- **美国SEC/CFTC等监管机构** (Controller): 通过注册报告获取市场数据，延迟公开执法信息；政策变化提前知晓
- **Bitcoin Core开发者** (Controller): 最先知道协议更新、BIP提案，影响网络规则
- **Chainalysis/TRM Labs等审计方** (Mediator): 分析链上数据，识别可疑交易，信息销售给监管和机构
- **大型做市商（Jump/GS等）** (Mediator): 通过算法交易和暗池掌握流动性深度，提前感知订单流
- **散户投资者** (Payer): 信息严重滞后，依赖公开新闻和社交媒体，容易成为信息劣势方

### Hidden Subsidies
- **德克萨斯州电网（ERCOT）** (Supplier): 通过需求响应计划向矿工支付电力信用，降低实际电力成本（如Riot 2025年12月获$6.2M）
- **美国政府（研发补贴/芯片法案）** (Controller): 间接补贴矿机芯片制造（台积电、三星获补贴），降低硬件成本
- **比特币网络通胀（区块奖励）** (Producer): 新铸造比特币向矿工支付，相当于所有持有者通过稀释承担成本（当前每日约450 BTC）
- **美国纳税人（战略比特币储备机会成本）** (Controller): 政府持有比特币未出售，承担价格下跌风险，相当于隐性补贴
- **ETF投资者（管理费）** (Payer): 持续支付管理费，补贴ETP发行商（如BlackRock、Grayscale）的运营
- **税收优惠（比特币支付免征州税提议）** (Controller): 某些州考虑对比特币支付免征资本利得税，补贴使用场景
- **跨境监管套利（少数国家政策）** (Controller): 如萨尔瓦多、巴拉圭等提供低税率或免税环境，吸引矿工迁入

### Mandatory Answers
- **Who subsidizes the system?** 比特币系统主要由三方面持续补贴：1）新铸造的比特币（区块奖励）补贴矿工，每4年减半，当前每日约450 BTC，价值约$32M；2）电网需求响应计划（如ERCOT）直接补贴矿工电力成本，2025年Riot一家获得约$6.2M/月；3）美国政府通过芯片法案、战略比特币储备等间接补贴。此外，ETF投资者通过管理费补贴发行商，零售矿工在高电价下亏损运营实则补贴工业矿工的市场份额。
- **Where does risk concentrate?** 风险最终集中在比特币持有者（Payer）和矿工（Producer）身上。持有者承受价格波动、监管不确定性和量子计算等尾风险；矿工（特别是零售矿工）在高难度、低币价下亏损运营，工业矿工通过AI转型分散风险。此外，系统性风险（如交易所黑客）集中在中介平台，而衍生品市场的杠杆风险在清算所积聚。
- **Is profit separated from risk?** 利润与风险部分分离。交易所（Mediator）赚取稳定手续费，但承担黑客和监管风险（如Bybit被盗）；ETP发行商（如Grayscale）赚取管理费，风险转移给投资者；矿机制造商（Supplier）赚取硬件利润但不承担币价风险。最大分离出现在矿工：在2026年价格$71k时，低成本工业矿工（如Riot）盈利$25k-$46k/BTC，而零售矿工亏损$4k-$41k/BTC，同样挖矿却承担不对称风险。此外，衍生品市场（如期货）允许投机者转移价格风险，但自身面临杠杆清算风险。

---

## 3. Power Map

- **Pricing Power**: Mediator（交易所、ETP做市商）通过订单簿交易和ETP发行主导价格发现；期货市场（如CME）影响短期定价；矿工生产成本提供长期价格下限，但影响力有限。
- **Entry Control**: Controller（监管机构：SEC/CFTC通过牌照注册、KYC/AML要求及市场结构立法）及Mediator（交易所的上币审查与合规筛选）共同控制市场准入；矿池的算力集中也构成软性进入壁垒。
- **Data Control**: Mediator（交易所掌握交易数据、用户KYC信息、链下流动性数据）；Controller（监管通过报告要求获取链上/链下数据）；Chainalysis等审计方分析链上数据。
- **Switching Cost**: Mediator（交易所/托管人通过KYC绑定、税务报告复杂性、忠诚度计划、API集成）提高用户切换成本；比特币自身地址转移虽无成本，但合规审核和历史记录绑定形成粘性。
- **Standard Control**: Controller（监管机构定义合规标准如MiCA、CLARITY法案；FASB制定会计准则；Bitcoin Core开发者定义协议标准BIPs）及Producer（矿工通过算力投票决定软分叉升级）。

---

## 4. Risk Map

- **比特币持有者（个人/机构/ETF/企业金库）** (Payer): 承担价格波动风险（2025年从$124k跌至$86k）、尾风险（量子计算、监管突变）
- **交易所（Binance/Coinbase/Kraken）** (Mediator): 承担黑客攻击风险（2025年Bybit被盗$1.46B）、监管罚款、流动性枯竭
- **矿工（特别是零售矿工）** (Producer): 承担价格风险、电力成本波动、硬件淘汰；零售矿工在$71k下亏损（成本$75k-$112k）
- **稳定币发行商（Tether/Circle）** (Mediator): 承担储备资产风险、赎回挤兑风险，但通过投资美债赚取收益
- **矿机制造商（Bitmain等）** (Supplier): 承担技术迭代风险（如量子计算）、供应链风险，但风险相对较低
- **美国联邦政府（战略比特币储备）** (Controller): 通过没收资产持有比特币，账面波动风险由纳税人承担
- **衍生品市场参与者（杠杆多头）** (Payer): 承担强制平仓风险，2025年期权净delta暴露崩溃

- **Risk Concentration**: 风险最终集中在比特币持有者（Payer）和矿工（Producer）身上。持有者承受价格波动、监管不确定性和量子计算等尾风险；矿工（特别是零售矿工）在高难度、低币价下亏损运营，工业矿工通过AI转型分散风险。此外，系统性风险（如交易所黑客）集中在中介平台，而衍生品市场的杠杆风险在清算所积聚。
- **Profit-Risk Separation**: 利润与风险部分分离。交易所（Mediator）赚取稳定手续费，但承担黑客和监管风险（如Bybit被盗）；ETP发行商（如Grayscale）赚取管理费，风险转移给投资者；矿机制造商（Supplier）赚取硬件利润但不承担币价风险。最大分离出现在矿工：在2026年价格$71k时，低成本工业矿工（如Riot）盈利$25k-$46k/BTC，而零售矿工亏损$4k-$41k/BTC，同样挖矿却承担不对称风险。此外，衍生品市场（如期货）允许投机者转移价格风险，但自身面临杠杆清算风险。

---

## 5. Score Vector

### Industry-Level Scores (0-10)

| Dimension | Score |
|-----------|-------|
| Control | 7.0 |
| Profit Capture | 6.0 |
| Risk Displacement | 5.0 |
| Information Advantage | 7.0 |
| Incentive Alignment | 7.0 |

### Company Rankings

| Company | Role | Control | Profit | Risk Disp | Info Adv | Incentive | Health |
|---------|------|---------|--------|-----------|----------|-----------|--------|
| Coinbase | Mediator | 7.0 | 8.0 | 5.0 | 8.0 | 6.0 | 49.78 |
| Bitmain | Supplier | 8.0 | 7.0 | 6.0 | 7.0 | 6.0 | 49.00 |
| MARA Holdings | Producer | 5.0 | 5.0 | 4.0 | 6.0 | 6.0 | 15.00 |
| Strategy (MSTR) | Payer | 4.0 | 5.0 | 3.0 | 5.0 | 7.0 | 10.00 |

---

## 6. Structural Phase

**Phase**: `mature`

**Reasoning Signals**:
- 比特币主导率在53%-64%之间波动，市场领导地位稳固
- 波动率压缩，从历史高点回撤未超过30%
- ETF和机构持有超过7%的流通供应，机构需求超过减半供应冲击7倍
- 监管清晰度提高（CLARITY法案、GENIUS法案），准入壁垒上升
- 矿工收入分化：工业矿工盈利（$25k-$46k/BTC），零售矿工亏损（-$4k到-$41k/BTC）
- 矿工转向AI/HPC基础设施，收入来源多样化
- 交易所向全能银行转型，整合传统金融业务

---

## 7. Key Fragilities

- ⚠️ Hidden subsidy dependency: 德克萨斯州电网（ERCOT）, 美国政府（研发补贴/芯片法案）, 比特币网络通胀（区块奖励）, 美国纳税人（战略比特币储备机会成本）, ETF投资者（管理费）, 税收优惠（比特币支付免征州税提议）, 跨境监管套利（少数国家政策） — system may not be self-sustaining

---

## Gate Validation

- ✅ **Gate1_ControlIdentified**: All 5 power dimensions attributed to roles, 4 roles identified.
- ✅ **Gate2_RiskAttribution**: Risk accumulation points identified, profit/risk attribution answered.
- ✅ **Gate3_InfoAsymmetry**: Information asymmetry identified at 8 nodes.
- ✅ **Gate4_HiddenFlows**: Hidden flows checked: subsidy_answer=yes, hidden_sources=7, value_capture_points=8.
- ✅ **Gate5_ComparableOutput**: Comparable output: industry_score=yes, companies_scored=4, phase=mature.
- ❌ **EntityGrounding**: 17/42 entities grounded in collected data (40%). Not found: F2Pool, Antpool, 其他大型矿池（如Foundry USA, Braiins）, 个人投资者, 机构投资者
- ✅ **ScoreQuality**: Score diversity: 3 unique industry values, health variance: 343.42, companies ranked: 4, unique company score sets: 4
- ✅ **FlowCompleteness**: Cash flow: 9 nodes, Info asymmetry: 8 nodes, Risk points: 7, Value capture: 8
- ✅ **RoleAttribution**: All 5 power dimensions attributed to specific roles
- ❌ **CrossLayerConsistency**: L2 orphans: 稳定币发行商（Tether/Circle）, 低成本工业矿工（Riot等）, 矿工（MARA/Riot）, 散户投资者, 衍生品清算所（如CME）

**⚠️ Failed gates: EntityGrounding, CrossLayerConsistency** — Output may be incomplete.