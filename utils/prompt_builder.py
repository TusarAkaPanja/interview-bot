"""
Prompt engineering - separated from business logic.
Builds prompts for different use cases.
"""
from typing import Dict
from .prompt_sanitizer import PromptSanitizer


class PromptBuilder:
    """Builds prompts for LLM interactions"""
    
    @staticmethod
    def build_greeting_prompt(
        panel_name: str,
        candidate_name: str,
        panel_description: str,
        total_questions: int
    ) -> str:
        """
        Build prompt for greeting generation.
        
        Args:
            panel_name: Name of interview panel
            candidate_name: Name of candidate
            panel_description: Panel description
            total_questions: Total number of questions
            
        Returns:
            Formatted prompt string
        """
        # Sanitize inputs
        panel_name = PromptSanitizer.sanitize_string(panel_name, max_length=200)
        candidate_name = PromptSanitizer.sanitize_string(candidate_name, max_length=100)
        panel_description = PromptSanitizer.sanitize_string(panel_description or 'Technical interview assessment', max_length=500)
        
        prompt = f"""You are a professional interviewer conducting a technical interview.

Interview Panel Details:
- Your Name: Vecna
- Name: {panel_name}
- Candidate Name: {candidate_name}
- Description: {panel_description}
- Total Questions: {total_questions}

Generate a warm, professional, and welcoming greeting message for the candidate.
The greeting should:
1. Greet the candidate by name, And Introduce yourself as Vecna.
2. Briefly mention the interview panel name
3. Set a friendly and professional tone
4. Explain that this is a voice-based interview
5. Be concise (2-3 sentences maximum)
6. Encourage the candidate to speak naturally.

Return ONLY the greeting text, nothing else. No prefixes, no explanations.
"""
        return prompt
    
    @staticmethod
    def build_analysis_prompt(
        question_text: str,
        expected_answer: str,
        expected_keywords: list,
        difficulty_level: str,
        red_flags: list,
        transcription: str,
        questions_asked: int,
        total_questions: int,
        expected_keywords_coverage: float,
        expected_time_in_seconds: int,
        ideal_answer_summary: str,
        total_time_taken_in_seconds: int,
        score_weight_technical: float,
        score_weight_domain_knowledge: float,
        score_weight_communication: float,
        score_weight_problem_solving: float,
        score_weight_creativity: float,
        score_weight_attention_to_detail: float,
        score_weight_time_management: float,
        score_weight_stress_management: float,
        score_weight_adaptability: float,
        score_weight_confidence: float
    ) -> str:
        # Sanitize inputs
        question_text = PromptSanitizer.sanitize_string(question_text, max_length=1000)
        expected_answer = PromptSanitizer.sanitize_string(expected_answer or "", max_length=2000)
        transcription = PromptSanitizer.sanitize_transcription(transcription)
        
        keywords_str = ', '.join(expected_keywords[:20]) if expected_keywords else 'None'
        red_flags_str = ', '.join(red_flags[:20]) if red_flags else 'None'

        expected_technical_competency = score_weight_technical + score_weight_domain_knowledge + score_weight_problem_solving
        expected_behavioral_and_soft_skills_competency = score_weight_communication + score_weight_creativity + score_weight_attention_to_detail + score_weight_time_management + score_weight_stress_management + score_weight_adaptability + score_weight_confidence
        expected_psychological_traits_competency = score_weight_confidence + score_weight_stress_management
        
        questions_percentage = (questions_asked / total_questions * 100) if total_questions > 0 else 0
        
        prompt = f"""You are an expert interviewer analyzing a candidate's answer.

Question: {question_text}
Expected Answer: {expected_answer}
Expected Keywords: {keywords_str}
Difficulty Level: {difficulty_level}
Red Flags to Watch: {red_flags_str}
Expected Technical Competency: {expected_technical_competency}
Expected Behavioral and Soft Skills Competency: {expected_behavioral_and_soft_skills_competency}
Expected Psychological Traits Competency: {expected_psychological_traits_competency}
Expected Keywords Coverage: {expected_keywords_coverage}
Expected Time in Seconds: {expected_time_in_seconds}
Ideal Answer Summary: {ideal_answer_summary}
Candidate's Answer (Transcription): {transcription}
Total Time Taken in Seconds: {total_time_taken_in_seconds}

Analyze this answer and provide:
1. Technical understanding score (0-1.0)
2. Domain knowledge score (0-1.0)
3. Communication clarity score (0-1.0)
4. Problem-solving ability score (0-1.0)
5. Creativity score (0-1.0)
6. Attention to detail score (0-1.0)
7. Time management score (0-1.0)
8. Stress management score (0-1.0)
9. Adaptability score (0-1.0)
10. Confidence score (0-1.0)
11. Keywords matched from expected keywords
12. Keywords coverage percentage (0-1.0)
13. Red flags detected
14. Overall analysis summary
15. Next action recommendation: "drill_up" (ask harder), "drill_down" (ask easier), "keep_level_same", or "end_of_interview" (only if 50%+ questions asked)


Questions asked so far: {questions_asked}
Total questions available: {total_questions}
Percentage asked: {questions_percentage:.1f}%

based on the expected competencies, calculate the scores and next action for the candidate's answer and return the scores and next action in the JSON response.
Return your response as JSON with this structure:
{{
    "score_technical": 0.85,
    "score_domain_knowledge": 0.80,
    "score_communication": 0.90,
    "score_problem_solving": 0.75,
    "score_creativity": 0.70,
    "score_attention_to_detail": 0.85,
    "score_time_management": 0.80,
    "score_stress_management": 0.75,
    "score_adaptability": 0.80,
    "score_confidence": 0.85,
    "keywords_matched": ["keyword1", "keyword2"],
    "keywords_coverage": 0.75,
    "red_flags_detected": [],
    "analysis_summary": "The candidate demonstrated strong technical understanding...",
    "next_action": "drill_up"
}}

IMPORTANT: Only recommend "end_of_interview" if at least 50% of questions have been asked.
"""
        return prompt

