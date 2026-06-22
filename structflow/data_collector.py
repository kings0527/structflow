"""Data collection layer: Tavily search + LLM web search integration."""

from __future__ import annotations

from typing import Optional

from tavily import TavilyClient

from structflow.config import config


class DataCollector:
    """Collects real-world data via Tavily API for industry analysis."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.tavily.api_key
        if not self.api_key:
            raise ValueError(
                "Tavily API key not configured. Set TAVILY_API_KEY in .env or pass --tavily-key"
            )
        self.client = TavilyClient(api_key=self.api_key)

    def search_industry(
        self,
        industry: str,
        region: Optional[str] = None,
        topics: Optional[list[str]] = None,
    ) -> str:
        """Search for industry data and return structured context."""
        query = self._build_query(industry, region, topics)
        response = self.client.search(
            query=query,
            search_depth=config.data.search_depth,
            max_results=config.data.search_max_results,
            include_answer=True,
        )
        return self._format_results(response)

    def search_company(
        self,
        company_name: str,
        industry: str,
    ) -> str:
        """Search for company-specific data."""
        query = f"{company_name} {industry} revenue market share business model 2024 2025"
        response = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
        )
        return self._format_results(response)

    def search_policy(
        self,
        industry: str,
        region: Optional[str] = None,
    ) -> str:
        """Search for policy and regulatory data."""
        region_str = f" in {region}" if region else ""
        query = f"{industry} policy regulation government subsidy{region_str} 2024 2025"
        response = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
        )
        return self._format_results(response)

    def _build_query(
        self,
        industry: str,
        region: Optional[str],
        topics: Optional[list[str]],
    ) -> str:
        """Build search query from parameters."""
        parts = [industry]
        if region:
            parts.append(region)
        parts.append("industry structure market share competition 2024 2025")
        if topics:
            parts.extend(topics)
        return " ".join(parts)

    def _format_results(self, response: dict) -> str:
        """Format Tavily response into structured context string."""
        lines = []

        if response.get("answer"):
            lines.append(f"## Summary\n{response['answer']}\n")

        results = response.get("results", [])
        if results:
            lines.append("## Sources\n")
            for i, result in enumerate(results, 1):
                title = result.get("title", "Untitled")
                url = result.get("url", "")
                content = result.get("content", "")
                lines.append(f"### {i}. {title}")
                lines.append(f"URL: {url}")
                lines.append(f"Content: {content}\n")

        return "\n".join(lines)

    def collect_all(
        self,
        industry: str,
        region: Optional[str] = None,
        peer_set: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """Collect all data needed for a full scan."""
        data = {
            "industry_overview": self.search_industry(industry, region),
            "policy_context": self.search_policy(industry, region),
        }

        if peer_set:
            company_data = {}
            for company in peer_set:
                company_data[company] = self.search_company(company, industry)
            data["company_profiles"] = company_data

        return data
