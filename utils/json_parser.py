"""
Robust JSON parsing from LLM responses.
Handles various formats and edge cases.
"""
import json
import re
import logging
from typing import Dict, Optional
from .exceptions import JSONParseError

logger = logging.getLogger(__name__)


class JSONParser:
    """Robust JSON parser for LLM responses"""
    
    @staticmethod
    def extract_json(text: str) -> str:
        if not text:
            raise JSONParseError("Empty text provided")
        
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()
        
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0).strip()
        
        return text.strip()
    
    @staticmethod
    def parse_llm_response(response_text: str, required_fields: Optional[list] = None) -> Dict:
        if not response_text:
            raise JSONParseError("Empty response text")
        
        try:
            json_text = JSONParser.extract_json(response_text)
            json_text = json_text.replace('```json', '').replace('```', '').strip()
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            parsed = json.loads(json_text)
            
            if not isinstance(parsed, dict):
                raise JSONParseError(f"Expected dict, got {type(parsed)}")
            
            if required_fields:
                missing_fields = [field for field in required_fields if field not in parsed]
                if missing_fields:
                    raise JSONParseError(
                        f"Missing required fields: {missing_fields}. "
                        f"Got: {list(parsed.keys())}"
                    )
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            logger.error(f"Failed to parse: {json_text[:500] if 'json_text' in locals() else response_text[:500]}")
            raise JSONParseError(f"Failed to parse JSON: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {str(e)}")
            raise JSONParseError(f"Unexpected parsing error: {str(e)}") from e

