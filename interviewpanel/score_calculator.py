"""
Score calculation with proper weight normalization.
Ensures weights sum to 1.0 for consistent scoring.
"""
import logging
from typing import Dict, Optional
from utils.exceptions import ScoreCalculationError

logger = logging.getLogger(__name__)


class ScoreCalculator:
    """Calculate weighted scores with proper normalization"""
    
    @staticmethod
    def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize weights to sum to 1.0.
        
        Args:
            weights: Dictionary of skill -> weight
            
        Returns:
            Normalized weights dictionary
        """
        total_weight = sum(weights.values())
        
        if total_weight == 0:
            logger.warning("All weights are zero, using equal weights")
            # Fallback: equal weights
            num_skills = len(weights)
            return {skill: 1.0 / num_skills for skill in weights}
        
        if abs(total_weight - 1.0) > 0.01:  # Allow small floating point errors
            logger.warning(
                f"Weights don't sum to 1.0 (sum={total_weight:.4f}), normalizing"
            )
        
        # Normalize
        return {skill: weight / total_weight for skill, weight in weights.items()}
    
    @staticmethod
    def calculate_weighted_score(
        scores: Dict[str, float],
        weights: Dict[str, float],
        normalize: bool = True
    ) -> float:
        """
        Calculate weighted total score.
        
        Args:
            scores: Dictionary of skill -> score (0-100)
            weights: Dictionary of skill -> weight (will be normalized if normalize=True)
            normalize: Whether to normalize weights to sum to 1.0
            
        Returns:
            Weighted total score (0-100)
            
        Raises:
            ScoreCalculationError: If calculation fails
        """
        if not scores:
            raise ScoreCalculationError("No scores provided")
        
        if not weights:
            raise ScoreCalculationError("No weights provided")
        
        # Normalize weights if requested
        if normalize:
            weights = ScoreCalculator.normalize_weights(weights)
        
        # Calculate weighted sum
        total_score = 0.0
        for skill, score in scores.items():
            if skill not in weights:
                logger.warning(f"Skill '{skill}' has score but no weight, skipping")
                continue
            
            # Validate score range (0-100)
            if score < 0 or score > 100:
                logger.warning(f"Score {score} for {skill} out of range [0-100], clamping")
                score = max(0, min(100, score))
            
            weight = weights[skill]
            total_score += score * weight
        
        # Ensure result is in valid range
        total_score = max(0, min(100, total_score))
        
        return round(total_score, 2)
    
    @staticmethod
    def validate_analysis_scores(analysis: Dict) -> Dict[str, float]:
        """
        Extract and validate score fields from analysis.
        
        Args:
            analysis: Analysis dictionary from LLM
            
        Returns:
            Dictionary of skill -> score
            
        Raises:
            ScoreCalculationError: If scores are invalid
        """
        score_fields = [
            'score_technical',
            'score_domain_knowledge',
            'score_communication',
            'score_problem_solving',
            'score_creativity',
            'score_attention_to_detail',
            'score_time_management',
            'score_stress_management',
            'score_adaptability',
            'score_confidence',
        ]
        
        scores = {}
        for field in score_fields:
            skill = field.replace('score_', '')
            score = analysis.get(field, 0)
            
            # Validate score type and range
            try:
                score = float(score)
                if score < 0 or score > 100:
                    logger.warning(f"Score {score} for {skill} out of range, clamping to [0-100]")
                    score = max(0, min(100, score))
                scores[skill] = score
            except (ValueError, TypeError):
                logger.warning(f"Invalid score value for {skill}: {score}, using 0")
                scores[skill] = 0
        
        return scores

