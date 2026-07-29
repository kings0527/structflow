# StructFlow Roadmap — 市场数据通道延后项

已交付：八个 provider（CFTC COT、FRED、DBnomics、EIA、Stooq/yfinance、
Binance/Coinbase/Kraken、SEC EDGAR、AkShare A股），fail-closed 契约与
三层权重体系见 `references/evidence-policy.md`。以下为评估后主动延后的
扩展项，每项附一句话价值与延后原因。

## 延后项清单

| 项目 | 价值 | 延后原因 |
|---|---|---|
| 港交所互联互通日度统计爬虫 | 北向/南向资金是 A 股与港股 L3 资金流的最强官方信号 | 无官方 API，页面结构改版频繁，爬虫维护成本高且 fail-closed 难保证 |
| JPX 投资者部门别买卖动向周报爬虫 | 外资/散户/机构分部位流向是日股拥挤度的一手官方数据 | 仅提供 Excel/PDF 周报下载，解析脆弱且滞后一周，优先级低于现有 COT 覆盖 |
| ESMA 净空头寄存器多平台聚合 | 欧盟 0.5% 以上净空头披露是欧股空头侧的唯一公开一手数据 | 数据分散在各国监管机构平台，格式不一，需逐国适配聚合层 |
| FINRA 做空数据 | 补齐美股空头侧（现由 COT + 13F 间接覆盖） | 半月频且结算滞后两个交易日，无官方 API 仅可爬取，已评估并明确不集成（见 evidence-policy），若 FINRA 发布官方 API 再启动 |
| CoinGecko 第三方校验层 | 为 ccxt 交易所直连价格增加独立聚合器交叉校验源 | 现有 Binance/Coinbase/Kraken 三所两两校验已满足双源要求，边际收益低且免费档限流严格 |
| LME/COMEX/SHFE 库存爬虫 | 金属显性库存是有色/贵金属供需与挤仓风险的核心指标 | LME 数据付费、COMEX 需解析每日 PDF/CSV 报表、SHFE 周报页面无 API，三所口径不一需先设计统一 schema |

## 排序原则

优先接入"官方 API + 免费 + 稳定 schema"的数据源（本期 DBnomics、EIA
即按此标准入选）；爬虫类一律延后，直至确认无官方 API 替代且价值足以
覆盖维护成本。任何新 provider 必须满足既有契约：懒加载、fail-closed、
滞后标注、`make_record` 格式契约、`analysis_date` 过滤。
