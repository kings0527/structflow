"""Score calibration: normalize scores for cross-model consistency."""

from __future__ import annotations

from structflow.models import CompanyScore, L3ScoringRanking, ScoreVector


class ScoreCalibrator:
    """Calibrates scores to reduce LLM-specific bias and improve cross-model consistency.
    
    Key principle: preserve relative differences between companies.
    Only normalize if scores are degenerate (all same, all extreme, or out of range).
    """

    @staticmethod
    def _is_degenerate(scores: list[float]) -> bool:
        """Check if scores are degenerate (no variance or all extreme)."""
        if len(scores) < 2:
            return False
        unique = len(set(scores))
        if unique <= 1:
            return True
        if all(s in (0, 10) for s in scores):
            return True
        return False

    @staticmethod
    def _clamp_score(score: float) -> float:
        """Clamp score to 0-10 range."""
        return max(0.0, min(10.0, round(score, 1)))

    @classmethod
    def calibrate_score_vector(cls, sv: ScoreVector) -> ScoreVector:
        """Calibrate a single score vector - only fix if degenerate."""
        scores = [
            sv.control_score,
            sv.profit_capture_score,
            sv.risk_displacement_score,
            sv.information_advantage_score,
            sv.incentive_alignment_score,
        ]

        # If scores are reasonable, just clamp and return
        if not cls._is_degenerate(scores):
            return ScoreVector(
                control_score=cls._clamp_score(sv.control_score),
                profit_capture_score=cls._clamp_score(sv.profit_capture_score),
                risk_displacement_score=cls._clamp_score(sv.risk_displacement_score),
                information_advantage_score=cls._clamp_score(sv.information_advantage_score),
                incentive_alignment_score=cls._clamp_score(sv.incentive_alignment_score),
            )

        # Degenerate case: spread scores evenly around mean=5
        mean_score = sum(scores) / len(scores)
        spread = 2.0
        offsets = [-2, -1, 0, 1, 2]
        calibrated = [cls._clamp_score(mean_score + offsets[i] * spread / 2) for i in range(5)]
        return ScoreVector(
            control_score=calibrated[0],
            profit_capture_score=calibrated[1],
            risk_displacement_score=calibrated[2],
            information_advantage_score=calibrated[3],
            incentive_alignment_score=calibrated[4],
        )

    @staticmethod
    def recalculate_structural_health(company: CompanyScore) -> float:
        """Recalculate structural health using the standard formula."""
        sv = company.score_vector
        numerator = sv.control_score * sv.profit_capture_score * sv.information_advantage_score
        denominator = sv.risk_displacement_score + (10 - sv.incentive_alignment_score)
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, 2)

    @classmethod
    def calibrate_l3(cls, l3: L3ScoringRanking) -> L3ScoringRanking:
        """Calibrate all scores in L3 output for consistency.
        
        Strategy: 
        1. Only normalize if scores are degenerate
        2. Preserve relative differences between companies
        3. Recalculate structural health from calibrated scores
        """
        # Calibrate industry score
        calibrated_industry_score = cls.calibrate_score_vector(l3.industry_score)

        # Calibrate company scores - preserve original differences
        calibrated_companies = []
        for company in l3.companies_ranked:
            calibrated_sv = cls.calibrate_score_vector(company.score_vector)
            new_health = cls.recalculate_structural_health(
                CompanyScore(
                    name=company.name,
                    role=company.role,
                    score_vector=calibrated_sv,
                    structural_health=0,
                )
            )
            calibrated_companies.append(
                CompanyScore(
                    name=company.name,
                    role=company.role,
                    score_vector=calibrated_sv,
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
