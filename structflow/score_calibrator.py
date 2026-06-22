"""Score calibration: normalize scores for cross-model consistency."""

from __future__ import annotations

from structflow.models import CompanyScore, L3ScoringRanking, ScoreVector


class ScoreCalibrator:
    """Calibrates scores to reduce LLM-specific bias and improve cross-model consistency."""

    @staticmethod
    def normalize_score_vector(score_vector: ScoreVector) -> ScoreVector:
        """Normalize a score vector to have mean=5 and reasonable variance."""
        scores = [
            score_vector.control_score,
            score_vector.profit_capture_score,
            score_vector.risk_displacement_score,
            score_vector.information_advantage_score,
            score_vector.incentive_alignment_score,
        ]

        mean_score = sum(scores) / len(scores)
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5 if variance > 0 else 1.0

        # Normalize to mean=5, std=2 (reasonable range for 0-10 scale)
        def normalize(s: float) -> float:
            if std_dev == 0:
                return 5.0
            normalized = ((s - mean_score) / std_dev) * 2 + 5
            return max(0, min(10, normalized))

        return ScoreVector(
            control_score=round(normalize(score_vector.control_score), 1),
            profit_capture_score=round(normalize(score_vector.profit_capture_score), 1),
            risk_displacement_score=round(normalize(score_vector.risk_displacement_score), 1),
            information_advantage_score=round(normalize(score_vector.information_advantage_score), 1),
            incentive_alignment_score=round(normalize(score_vector.incentive_alignment_score), 1),
        )

    @staticmethod
    def recalculate_structural_health(company: CompanyScore) -> float:
        """Recalculate structural health using the standard formula."""
        sv = company.score_vector
        # Formula: (Control × ProfitCapture × InfoAdvantage) ÷ (RiskDisplacement + (10 - IncentiveAlignment))
        numerator = sv.control_score * sv.profit_capture_score * sv.information_advantage_score
        denominator = sv.risk_displacement_score + (10 - sv.incentive_alignment_score)
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, 2)

    @classmethod
    def calibrate_l3(cls, l3: L3ScoringRanking) -> L3ScoringRanking:
        """Calibrate all scores in L3 output for consistency."""
        # Normalize industry score
        calibrated_industry_score = cls.normalize_score_vector(l3.industry_score)

        # Normalize and recalculate company scores
        calibrated_companies = []
        for company in l3.companies_ranked:
            normalized_sv = cls.normalize_score_vector(company.score_vector)
            new_health = cls.recalculate_structural_health(
                CompanyScore(
                    name=company.name,
                    role=company.role,
                    score_vector=normalized_sv,
                    structural_health=0,
                )
            )
            calibrated_companies.append(
                CompanyScore(
                    name=company.name,
                    role=company.role,
                    score_vector=normalized_sv,
                    structural_health=new_health,
                )
            )

        # Sort by structural health (descending)
        calibrated_companies.sort(key=lambda c: c.structural_health, reverse=True)

        return L3ScoringRanking(
            industry_score=calibrated_industry_score,
            companies_ranked=calibrated_companies,
            phase=l3.phase,
        )
