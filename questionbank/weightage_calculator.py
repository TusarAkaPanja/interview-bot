import re
import math
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class WeightageCalculator:
    """Calculate score weightages for questions using formulas based on question content"""
    
    # Base weights for different question types
    BASE_WEIGHTS = {
        'technical': 0.5,
        'domain_knowledge': 0.3,
        'communication': 0.1,
        'problem_solving': 0.05,
        'creativity': 0.05,
        'attention_to_detail': 0.05,
        'time_management': 0.05,
        'stress_management': 0.05,
        'adaptability': 0.05,
        'confidence': 0.05
    }
    
    # Keywords that indicate different skill areas
    SKILL_KEYWORDS = {
        'technical': [
            'code', 'algorithm', 'implementation', 'syntax', 'framework',
            'library', 'api', 'database', 'architecture', 'design pattern',
            'optimization', 'performance', 'debugging', 'testing'
        ],
        'domain_knowledge': [
            'concept', 'principle', 'theory', 'best practice', 'standard',
            'methodology', 'approach', 'industry', 'domain', 'expertise'
        ],
        'communication': [
            'explain', 'describe', 'present', 'communicate', 'document',
            'articulate', 'clarify', 'discuss', 'presentation'
        ],
        'problem_solving': [
            'solve', 'problem', 'challenge', 'issue', 'troubleshoot',
            'debug', 'analyze', 'investigate', 'resolve', 'approach'
        ],
        'creativity': [
            'innovative', 'creative', 'design', 'approach', 'solution',
            'alternative', 'unique', 'novel', 'imagination'
        ],
        'attention_to_detail': [
            'detail', 'specific', 'precise', 'accurate', 'thorough',
            'meticulous', 'careful', 'exact', 'precise'
        ],
        'time_management': [
            'time', 'deadline', 'schedule', 'prioritize', 'efficient',
            'quick', 'timely', 'urgent'
        ],
        'stress_management': [
            'pressure', 'stress', 'difficult', 'challenging', 'complex',
            'critical', 'urgent', 'demanding'
        ],
        'adaptability': [
            'adapt', 'change', 'flexible', 'modify', 'adjust',
            'evolve', 'update', 'migrate', 'transition'
        ],
        'confidence': [
            'confident', 'certain', 'sure', 'definitive', 'assert',
            'convince', 'persuade', 'assure'
        ]
    }
    
    @staticmethod
    def calculate_keyword_density(text: str, keywords: List[str]) -> float:
        """Calculate the density of keywords in text"""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        keyword_count = sum(1 for keyword in keywords if keyword.lower() in text_lower)
        word_count = len(text.split())
        
        if word_count == 0:
            return 0.0
        
        return keyword_count / word_count
    
    @staticmethod
    def calculate_complexity_score(question: str, expected_answer: str) -> float:
        """Calculate question complexity based on length and structure"""
        question_words = len(question.split())
        answer_words = len(expected_answer.split())
        
        # Normalize to 0-1 scale
        question_complexity = min(question_words / 100, 1.0)
        answer_complexity = min(answer_words / 500, 1.0)
        
        # Average complexity
        return (question_complexity + answer_complexity) / 2
    
    @staticmethod
    def calculate_difficulty_multiplier(difficulty: str) -> Dict[str, float]:
        """Get multipliers for different skills based on difficulty"""
        multipliers = {
            'easy': {
                'technical': 0.8,
                'domain_knowledge': 1.0,
                'communication': 1.2,
                'problem_solving': 0.7,
                'creativity': 0.6,
                'attention_to_detail': 0.9,
                'time_management': 1.1,
                'stress_management': 0.8,
                'adaptability': 0.7,
                'confidence': 1.2
            },
            'medium': {
                'technical': 1.0,
                'domain_knowledge': 1.0,
                'communication': 1.0,
                'problem_solving': 1.0,
                'creativity': 1.0,
                'attention_to_detail': 1.0,
                'time_management': 1.0,
                'stress_management': 1.0,
                'adaptability': 1.0,
                'confidence': 1.0
            },
            'hard': {
                'technical': 1.3,
                'domain_knowledge': 1.2,
                'communication': 0.9,
                'problem_solving': 1.4,
                'creativity': 1.3,
                'attention_to_detail': 1.1,
                'time_management': 0.9,
                'stress_management': 1.2,
                'adaptability': 1.1,
                'confidence': 0.9
            }
        }
        return multipliers.get(difficulty.lower(), multipliers['medium'])
    
    @classmethod
    def calculate_weightages(
        cls,
        question: str,
        expected_answer: str,
        keywords: List[str],
        difficulty: str
    ) -> Dict[str, float]:
        """Calculate all weightages for a question"""
        
        # Combine question and answer for analysis
        combined_text = f"{question} {expected_answer}"
        
        # Calculate keyword densities for each skill
        skill_scores = {}
        for skill, skill_keywords in cls.SKILL_KEYWORDS.items():
            density = cls.calculate_keyword_density(combined_text, skill_keywords)
            skill_scores[skill] = density
        
        # Calculate complexity
        complexity = cls.calculate_complexity_score(question, expected_answer)
        
        # Get difficulty multipliers
        difficulty_multipliers = cls.calculate_difficulty_multiplier(difficulty)
        
        # Calculate base weights with adjustments
        weights = {}
        total_weight = 0.0
        
        for skill, base_weight in cls.BASE_WEIGHTS.items():
            # Start with base weight
            weight = base_weight
            
            # Adjust based on keyword density (0 to 0.3 adjustment)
            keyword_adjustment = skill_scores[skill] * 0.3
            
            # Adjust based on complexity (for technical and problem solving)
            if skill in ['technical', 'problem_solving']:
                complexity_adjustment = complexity * 0.2
            else:
                complexity_adjustment = 0
            
            # Apply difficulty multiplier
            difficulty_mult = difficulty_multipliers[skill]
            
            # Calculate final weight
            weight = (weight + keyword_adjustment + complexity_adjustment) * difficulty_mult
            weights[skill] = weight
            total_weight += weight
        
        # Normalize weights to sum to 1.0
        if total_weight > 0:
            for skill in weights:
                weights[skill] = weights[skill] / total_weight
        else:
            # Fallback to base weights if calculation fails
            weights = cls.BASE_WEIGHTS.copy()
        
        # Map to model field names with 2 decimal precision
        return {
            'score_weight_technical': round(weights.get('technical', 0.5), 2),
            'score_weight_domain_knowledge': round(weights.get('domain_knowledge', 0.3), 2),
            'score_weight_communication': round(weights.get('communication', 0.1), 2),
            'score_weight_problem_solving': round(weights.get('problem_solving', 0.05), 2),
            'score_weight_creativity': round(weights.get('creativity', 0.05), 2),
            'score_weight_attention_to_detail': round(weights.get('attention_to_detail', 0.05), 2),
            'score_weight_time_management': round(weights.get('time_management', 0.05), 2),
            'score_weight_stress_management': round(weights.get('stress_management', 0.05), 2),
            'score_weight_adaptability': round(weights.get('adaptability', 0.05), 2),
            'score_weight_confidence': round(weights.get('confidence', 0.05), 2)
        }
    
    @staticmethod
    def calculate_keywords_coverage(keywords: List[str], expected_answer: str) -> float:
        """Calculate expected keywords coverage percentage"""
        if not keywords or not expected_answer:
            return 0.1
        
        answer_lower = expected_answer.lower()
        found_keywords = sum(1 for keyword in keywords if keyword.lower() in answer_lower)
        
        return min(found_keywords / len(keywords), 1.0) if keywords else 0.1

