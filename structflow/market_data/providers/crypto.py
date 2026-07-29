"""Crypto data via ccxt direct exchange APIs (Tier 1-adjacent).

Binance and OKX spot prices cross-validate each other (natural dual
source); futures open interest and funding rate are first-hand
positioning signals, annotated as a single-exchange perspective.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from structflow.market_data.base import (
    ProviderResult,
    PriceObservation,
    build_price_records,
    content_header,
    cross_validate_price,
    make_record,
    provider_failure,
)


SINGLE_EXCHANGE_NOTE = "Binance/OKX 单交易所视角，非全市场口径"

EXCHANGE_URLS = {
    "binance": "https://www.binance.com/en/trade/{pair}",
    "okx": "https://www.okx.com/trade-spot/{pair_dash}",
}


def _exchange(exchange_id: str, timeout: float):
    """Instantiate one ccxt exchange client (lazy import)."""
    import ccxt  # noqa: PLC0415 — optional dependency

    return getattr(ccxt, exchange_id)({
        "timeout": int(timeout * 1000),
        "enableRateLimit": True,
    })


def _spot_ticker(
    exchange_id: str, symbol: str, timeout: float
) -> PriceObservation:
    """Last spot price straight from one exchange's public API."""
    client = _exchange(exchange_id, timeout)
    ticker = client.fetch_ticker(symbol)
    price = float(ticker.get("last") or ticker.get("close") or 0)
    if price <= 0:
        raise ValueError(
            f"{exchange_id} returned no last price for {symbol!r}"
        )
    timestamp = ticker.get("timestamp")
    observed_on = (
        datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).date()
        if timestamp
        else datetime.now(timezone.utc).date()
    )
    base, _, quote = symbol.partition("/")
    pair = f"{base}_{quote}"
    url = EXCHANGE_URLS[exchange_id].format(
        pair=pair, pair_dash=f"{base.lower()}-{quote.lower()}"
    )
    return PriceObservation(
        source=exchange_id,
        url=url,
        price=price,
        observed_on=observed_on,
        currency=quote or "USDT",
        volume=float(ticker.get("baseVolume") or 0) or None,
        upstream_origin=f"{exchange_id} exchange API",
    )


def _open_interest(
    exchange_id: str, symbol: str, timeout: float
) -> tuple[date, float]:
    """(observed_on, open interest in contracts/coins) for a swap."""
    client = _exchange(exchange_id, timeout)
    payload = client.fetch_open_interest(symbol)
    amount = float(
        payload.get("openInterestAmount")
        or payload.get("openInterestValue")
        or 0
    )
    if amount <= 0:
        raise ValueError(
            f"{exchange_id} returned no open interest for {symbol!r}"
        )
    timestamp = payload.get("timestamp")
    observed_on = (
        datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).date()
        if timestamp
        else datetime.now(timezone.utc).date()
    )
    return (observed_on, amount)


def _funding_rate(
    exchange_id: str, symbol: str, timeout: float
) -> tuple[date, float]:
    """(observed_on, current funding rate) for a perpetual swap."""
    client = _exchange(exchange_id, timeout)
    payload = client.fetch_funding_rate(symbol)
    rate = payload.get("fundingRate")
    if rate is None:
        raise ValueError(
            f"{exchange_id} returned no funding rate for {symbol!r}"
        )
    timestamp = payload.get("timestamp")
    observed_on = (
        datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).date()
        if timestamp
        else datetime.now(timezone.utc).date()
    )
    return (observed_on, float(rate))


def fetch_crypto(
    subject: str,
    code: str | None,
    analysis_date: date,
    *,
    tolerance: float = 0.005,
    timeout: float = 20.0,
    types: set[str] | None = None,
) -> ProviderResult:
    """Dual-exchange spot price plus OI and funding-rate records."""
    result = ProviderResult()
    symbol = (code or "").strip().upper()
    if symbol and "/" not in symbol:
        symbol = f"{symbol}/USDT"
    if not symbol:
        result.failures.append(provider_failure(
            "crypto", "code",
            "--code is required for crypto data (e.g. ETH/USDT)",
        ))
        return result
    wanted = types or {"price", "positioning", "funding"}
    base_asset = symbol.split("/", 1)[0]
    entity_label = f"{subject}（{base_asset}）"
    swap_symbol = f"{symbol}:USDT"

    if "price" in wanted:
        observations: list[PriceObservation] = []
        for exchange_id in ("binance", "okx"):
            try:
                observations.append(
                    _spot_ticker(exchange_id, symbol, timeout)
                )
            except Exception as error:
                result.failures.append(provider_failure(
                    "crypto", f"{exchange_id}_spot", error
                ))
        if len(observations) == 2:
            check = cross_validate_price(
                observations[0], observations[1], tolerance
            )
            if check["passed"]:
                result.cross_validation_passed.append(check)
                result.records.extend(build_price_records(
                    entity_label=entity_label,
                    query=f"{symbol} spot price",
                    observations=(observations[0], observations[1]),
                    source_type="market_data_official",
                    check=check,
                    note="Binance/OKX 官方 API 双交易所交叉校验",
                ))
            else:
                result.cross_validation_failed.append(check)
                result.degraded.append(
                    f"crypto: {symbol} 双交易所价格校验失败"
                    f"（{check['reason']}），价格记录未入库（fail-closed）"
                )
        else:
            result.degraded.append(
                f"crypto: {symbol} 仅 {len(observations)} 个交易所可用，"
                "不足双源校验，价格记录未入库（fail-closed）"
            )

    if "positioning" in wanted:
        try:
            observed_on, amount = _open_interest(
                "binance", swap_symbol, timeout
            )
            lag_days = max(0, (analysis_date - observed_on).days)
            lines = [
                content_header(
                    f"{entity_label} 永续合约未平仓量",
                    observed_on,
                    lag_days,
                ),
                f"Binance {swap_symbol} 未平仓量 {amount:,.0f} {base_asset}",
                SINGLE_EXCHANGE_NOTE,
            ]
            result.records.append(make_record(
                category="market_data_positioning",
                provider="market_data_ccxt_binance",
                query=f"{symbol} open interest",
                title=(
                    f"{entity_label} 未平仓量 {observed_on.isoformat()}"
                ),
                url=(
                    "https://www.binance.com/en/futures/funding-history/"
                    f"perpetual/{base_asset}USDT"
                ),
                content="\n".join(lines),
                published_at=observed_on.isoformat(),
                source_type="market_data_official",
                upstream_origin="binance exchange API",
            ))
        except Exception as error:
            result.failures.append(
                provider_failure("crypto", "open_interest", error)
            )
            result.degraded.append(
                f"crypto: {symbol} 未平仓量不可用（{type(error).__name__}）"
            )

    if "funding" in wanted:
        try:
            observed_on, rate = _funding_rate(
                "binance", swap_symbol, timeout
            )
            lag_days = max(0, (analysis_date - observed_on).days)
            lines = [
                content_header(
                    f"{entity_label} 永续合约资金费率",
                    observed_on,
                    lag_days,
                ),
                f"Binance {swap_symbol} 资金费率 {rate:+.4%}",
                SINGLE_EXCHANGE_NOTE,
            ]
            result.records.append(make_record(
                category="market_data_funding",
                provider="market_data_ccxt_binance",
                query=f"{symbol} funding rate",
                title=(
                    f"{entity_label} 资金费率 {observed_on.isoformat()}"
                ),
                url=(
                    "https://www.binance.com/en/futures/funding-history/"
                    f"perpetual/{base_asset}USDT/funding-fee"
                ),
                content="\n".join(lines),
                published_at=observed_on.isoformat(),
                source_type="market_data_official",
                upstream_origin="binance exchange API",
            ))
        except Exception as error:
            result.failures.append(
                provider_failure("crypto", "funding_rate", error)
            )
            result.degraded.append(
                f"crypto: {symbol} 资金费率不可用（{type(error).__name__}）"
            )
    return result
