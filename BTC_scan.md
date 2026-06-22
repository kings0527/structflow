# Industry Scan Report: BTC

**Time Horizon**: mid
**Core Need**: 提供一种去中心化、抗审查、固定供应量的数字价值存储与转移手段，满足全球用户对资产主权和避险的需求。
**Substitution Risk**: 0.45 | **Demand Stability**: 0.4 | **Narrative Dependency**: 0.85

---
## 1. Structure Map

### Producer
- **Entities**: Marathon Digital Holdings, Core Scientific, Riot Platforms, CleanSpark, Bit Digital, Foundry USA, MARA Pool
- **Description**: 通过挖矿产生新比特币并维护网络安全，矿工和矿池是直接的比特币生产者。

### Payer
- **Entities**: BlackRock (IBIT ETF), Fidelity (FBTC ETF), MicroStrategy (Strategy), 其他机构投资者和散户
- **Description**: 购买并持有比特币，包括通过ETF和直接持有，驱动需求端。

### Mediator
- **Entities**: Binance, Coinbase, Kraken, Bitfinex, Huobi, Gemini, OKEx, KuCoin
- **Description**: 提供交易、托管和流动性服务，连接生产者与买家，是市场流动性和价格发现的核心。

### Controller
- **Entities**: 美国SEC, 欧盟MiCA, Foundry USA (矿池), Bitcoin Core开发者, Bitmain (矿机标准)
- **Description**: 通过监管政策、协议规则、算力集中和硬件标准控制行业准入和运行规则。

---

## 2. Flow Map

### Cash Flow Chain
- **机构投资者（如BlackRock IBIT ETF）** (Payer): 通过ETF产品投入法币，购买比特币份额，法币进入ETF托管账户。
- **散户投资者** (Payer): 通过交易所（如Coinbase）直接买入比特币，法币汇入交易所账户。
- **交易所（Binance、Coinbase等）** (Mediator): 接收买家法币，撮合交易，向卖家（矿工或持币者）支付法币，并收取交易手续费。
- **矿池（Foundry USA、MARAPool等）** (Producer): 聚合算力获得区块奖励，通过OTC或交易所卖出比特币换取法币，扣除矿池费用后向矿工分配收益。
- **矿工（Marathon Digital、Riot Platforms等）** (Producer): 直接或通过矿池出售挖出的比特币，获得法币收入。
- **电力公司** (Other): 矿工支付电费，电力公司获得稳定现金流，电费占矿工运营成本主要部分。
- **矿机厂商（Bitmain、MicroBT等）** (Controller): 矿工购买矿机，Bitmain等厂商获得一次性硬件销售利润，控制硬件标准。

### Value Capture Points
- **交易所（Binance）** (Mediator): 通过交易手续费、上币费、衍生品交易费捕获价值，日交易量超千亿美元，手续费收入极高。
- **矿池（Foundry USA）** (Producer): 按算力贡献收取矿工手续费（约2-4%），稳定捕获价值，无价格风险。
- **矿机厂商（Bitmain）** (Controller): 占据82%矿机市场份额，销售高利润ASIC矿机，捕获硬件升级带来的价值。
- **托管机构（Coinbase Custody）** (Mediator): 为ETF和机构提供托管服务，收取托管费，基于资产规模收费，价值稳定。

### Information Asymmetry
- **Bitcoin Core开发者** (Controller): 最先知晓协议更新（如Taproot、软分叉），可影响网络规则。
- **矿池（Foundry USA）** (Producer): 实时掌握全网算力变化和自身算力占比，能预判挖矿难度调整。
- **交易所（Binance）** (Mediator): 拥有深度订单簿和用户交易数据，最先感知大额买卖和流动性变化。
- **矿机厂商（Bitmain）** (Controller): 掌握新型矿机效率和产能信息，能提前调整定价和生产策略。
- **散户投资者** (Payer): 信息延迟，主要依赖公开新闻和社交媒体，易受到误导。

### Hidden Subsidies
- **美国政府** (Controller): 通过行政令建立战略比特币储备，提供政策预期支撑；税收优惠（如矿机加速折旧）间接补贴挖矿。
- **电力市场（过剩能源）** (Other): 矿工利用弃风弃水或低电价地区电力，相当于获得隐性能源补贴，降低挖矿成本。
- **欧盟MiCA监管框架** (Controller): 统一监管降低合规成本，为交易所和托管机构提供制度红利。

### Mandatory Answers
- **Who subsidizes the system?** 系统基本自维持，无持续外部现金补贴。矿工通过挖矿获得新区块奖励（3.125 BTC/块）和交易费，这是系统内生的通胀补贴。美国政府通过战略储备和友好政策提供隐性需求支撑，但并非直接注资。
- **Where does risk concentrate?** 风险最终集中在矿工（Producer）和长期持有者（Payer）。矿工承受减半后收入减半、电费波动和硬件淘汰风险；持有者承受价格剧烈波动和流动性枯竭风险。交易所（Mediator）承担运营和监管风险但通过多样化分散。
- **Is profit separated from risk?** 利润与风险部分分离。矿机厂商（Bitmain）和矿池（Foundry USA）获取稳定收益，不直接承担比特币价格风险；交易所（Binance）手续费收入稳定但面临运营风险。矿工利润高度依赖于价格，风险完全暴露。因此，Bitmain和矿池是获利而不直接承担价格风险的主要角色。

---

## 3. Power Map

- **Pricing Power**: Mediator（交易所）通过订单簿撮合和流动性聚合主导比特币价格发现，矿工成本仅影响价格下限。
- **Entry Control**: Controller（监管机构如SEC、MiCA）通过牌照和合规要求控制合法进入，矿池通过算力集中控制挖矿准入。
- **Data Control**: Mediator（交易所）掌握交易量、用户KYC等核心数据，链上数据虽透明但交易所数据最具商业价值。
- **Switching Cost**: Controller（监管要求如KYC/AML）使得用户在交易所间切换需重复合规，增加迁移成本；比特币资产本身转移成本低。
- **Standard Control**: Controller（Bitcoin Core开发者）主导协议标准，Producer（Bitmain）通过82%矿机市场份额主导硬件标准。

---

## 4. Risk Map

- **矿工（Marathon、Riot等）** (Producer): 承受区块奖励减半、电费波动、矿机淘汰风险，2024年减半后日收入约3000万美元，但需持续升级设备。
- **交易所（Binance）** (Mediator): 面临黑客攻击、监管处罚、挤兑风险，历史上多次发生安全事件。
- **长期持有者（MicroStrategy）** (Payer): 承担比特币价格波动风险，但通过杠杆放大收益与损失，持有超过60万BTC。
- **ETF投资者** (Payer): 承担市场系统性风险和基金管理风险，但通过ETF获得合规敞口。

- **Risk Concentration**: 风险最终集中在矿工（Producer）和长期持有者（Payer）。矿工承受减半后收入减半、电费波动和硬件淘汰风险；持有者承受价格剧烈波动和流动性枯竭风险。交易所（Mediator）承担运营和监管风险但通过多样化分散。
- **Profit-Risk Separation**: 利润与风险部分分离。矿机厂商（Bitmain）和矿池（Foundry USA）获取稳定收益，不直接承担比特币价格风险；交易所（Binance）手续费收入稳定但面临运营风险。矿工利润高度依赖于价格，风险完全暴露。因此，Bitmain和矿池是获利而不直接承担价格风险的主要角色。

---

## 5. Score Vector

### Industry-Level Scores (0-10)

| Dimension | Score |
|-----------|-------|
| Control | 6.9 |
| Profit Capture | 5.5 |
| Risk Displacement | 6.9 |
| Information Advantage | 1.5 |
| Incentive Alignment | 4.2 |

### Company Rankings

| Company | Role | Control | Profit | Risk Disp | Info Adv | Incentive | Health |
|---------|------|---------|--------|-----------|----------|-----------|--------|
| MicroStrategy | Payer | 3.1 | 6.2 | 3.1 | 4.2 | 8.3 | 16.82 |
| Marathon Digital Holdings | Producer | 3.1 | 6.2 | 3.1 | 4.2 | 8.3 | 16.82 |
| Core Scientific | Producer | 3.1 | 6.2 | 3.1 | 4.2 | 8.3 | 16.82 |
| Riot Platforms | Producer | 3.1 | 6.2 | 3.1 | 4.2 | 8.3 | 16.82 |
| CleanSpark | Producer | 3.1 | 6.2 | 3.1 | 4.2 | 8.3 | 16.82 |
| Bit Digital | Producer | 3.1 | 6.2 | 3.1 | 4.2 | 8.3 | 16.82 |
| Binance | Mediator | 5.4 | 7.4 | 5.4 | 5.4 | 1.3 | 15.30 |
| Coinbase | Mediator | 4.0 | 9.0 | 4.0 | 4.0 | 4.0 | 14.40 |
| OKEx | Mediator | 3.4 | 7.4 | 3.4 | 3.4 | 7.4 | 14.26 |
| Bitmain | Controller | 8.2 | 5.5 | 5.5 | 2.9 | 2.9 | 10.38 |
| Foundry USA | Producer | 6.6 | 6.6 | 6.6 | 2.6 | 2.6 | 8.09 |
| Kraken | Mediator | 3.4 | 7.4 | 7.4 | 3.4 | 3.4 | 6.11 |
| Bitfinex | Mediator | 3.4 | 7.4 | 7.4 | 3.4 | 3.4 | 6.11 |
| BlackRock | Payer | 1.9 | 7.1 | 5.3 | 3.6 | 7.1 | 5.92 |
| Fidelity | Payer | 1.9 | 7.1 | 5.3 | 3.6 | 7.1 | 5.92 |
| Gemini | Mediator | 2.6 | 6.6 | 6.6 | 2.6 | 6.6 | 4.46 |
| Huobi | Mediator | 2.6 | 6.6 | 6.6 | 2.6 | 6.6 | 4.46 |
| KuCoin | Mediator | 2.6 | 6.6 | 6.6 | 2.6 | 6.6 | 4.46 |
| MARA Pool | Producer | 4.0 | 6.5 | 6.5 | 1.5 | 6.5 | 3.90 |

---

## 6. Structural Phase

**Phase**: `growth`

**Reasoning Signals**:
- 2024-2025年比特币市场CAGR达38.49%，市场容量从2.05万亿美元增至2.83万亿美元
- 现货比特币ETF获得批准，机构净流入超500亿美元，BlackRock和Fidelity的ETF规模领先
- MicroStrategy等企业持有BTC超92.3万枚，企业采用率同比增587%
- 矿工算力持续增长，Foundry USA算力占比36.5%，Bitmain矿机份额82%，显示控制集中
- 监管框架逐步清晰，美国通过GENIUS Act，欧盟MiCA全面实施，降低不确定性
- 减半后矿工日收入仍维持在约3000万美元，效率提升24%，基本面稳健
- Layer2网络交易量增长，扩展比特币应用场景

---

## 7. Key Fragilities

- ⚠️ High narrative/policy dependency (0.85): structural demand may collapse if narrative shifts
- ⚠️ Hidden subsidy dependency: 美国政府, 电力市场（过剩能源）, 欧盟MiCA监管框架 — system may not be self-sustaining

---

## Gate Validation

- ✅ **Gate1_ControlIdentified**: All 5 power dimensions attributed to roles, 4 roles identified.
- ✅ **Gate2_RiskAttribution**: Risk accumulation points identified, profit/risk attribution answered.
- ✅ **Gate3_InfoAsymmetry**: Information asymmetry identified at 5 nodes.
- ✅ **Gate4_HiddenFlows**: Hidden flows checked: subsidy_answer=yes, hidden_sources=3, value_capture_points=4.
- ✅ **Gate5_ComparableOutput**: Comparable output: industry_score=yes, companies_scored=19, phase=growth.
- ✅ **EntityGrounding**: 21/24 entities grounded in collected data (88%). Not found: 其他机构投资者和散户, 美国SEC, 欧盟MiCA
- ✅ **ScoreQuality**: Score diversity: 4 unique values, health variance: 27.89, companies ranked: 19
- ✅ **FlowCompleteness**: Cash flow: 7 nodes, Info asymmetry: 5 nodes, Risk points: 4, Value capture: 4
- ✅ **RoleAttribution**: All 5 power dimensions attributed to specific roles

**All gates passed.** Output is structurally valid and comparable.