import threading
import time
import logging
import difflib
from typing import Dict, Optional, Tuple
from django.db import transaction

from .models import (
    Question, QuestionConfiguration, QuestionConfigurationStatus,
    Category, Topic, Subtopic, DifficultyLevel
)
from .ollama_service import OllamaService
from .weightage_calculator import WeightageCalculator
from authentication.models import User

logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self):
        self.ollama_service = OllamaService()
        self.weightage_calculator = WeightageCalculator()
        self.similarity_threshold = 0.8
        self.question_similarity_threshold = 0.85
    
    def _find_similar_subtopic(
        self, 
        subtopic_name: str, 
        topic: Topic, 
        threshold: float = None
    ) -> Optional[Tuple[Subtopic, float]]:
        if threshold is None:
            threshold = self.similarity_threshold
        
        existing_subtopics = Subtopic.objects.filter(topic=topic)
        if not existing_subtopics.exists():
            return None
        
        normalized_search_name = subtopic_name.lower().strip()
        best_match = None
        best_ratio = 0.0
        
        for subtopic in existing_subtopics:
            normalized_subtopic_name = subtopic.name.lower().strip()
            ratio = difflib.SequenceMatcher(
                None, 
                normalized_search_name, 
                normalized_subtopic_name
            ).ratio()
            
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = subtopic
        
        if best_match:
            logger.info(
                f"Found similar subtopic: '{best_match.name}' "
                f"(similarity: {best_ratio:.2f}) for search term: '{subtopic_name}'"
            )
            return (best_match, best_ratio)
        
        return None
    
    def generate_questions_async(
        self,
        config_uuid: str,
        category_uuid: str,
        topic_uuid: str,
        subtopic_uuid: Optional[str],
        total_questions: int,
        difficulty_partitions: Dict[str, float],
        user: User
    ):
        logger.info(f"[CONFIG {config_uuid}] Starting async question generation thread")
        logger.info(f"[CONFIG {config_uuid}] Parameters: total={total_questions}, partitions={difficulty_partitions}")
        thread = threading.Thread(
            target=self._generate_questions,
            args=(
                config_uuid, category_uuid, topic_uuid, subtopic_uuid,
                total_questions, difficulty_partitions, user
            ),
            daemon=True
        )
        thread.start()
        logger.info(f"[CONFIG {config_uuid}] Thread started successfully")
    
    def _generate_questions(
        self,
        config_uuid: str,
        category_uuid: str,
        topic_uuid: str,
        subtopic_uuid: Optional[str],
        total_questions: int,
        difficulty_partitions: Dict[str, float],
        user: User
    ):
        start_time = time.time()
        logger.info(f"[CONFIG {config_uuid}] ========== QUESTION GENERATION STARTED ==========")
        logger.info(f"[CONFIG {config_uuid}] Thread ID: {threading.current_thread().ident}")
        logger.info(f"[CONFIG {config_uuid}] Total questions to generate: {total_questions}")
        logger.info(f"[CONFIG {config_uuid}] Difficulty partitions: {difficulty_partitions}")
        
        try:
            config = QuestionConfiguration.objects.get(uuid=config_uuid)
            logger.info(f"[CONFIG {config_uuid}] Found configuration: {config.name}")
            logger.info(f"[CONFIG {config_uuid}] Current status: {config.status}")
            
            config.status = QuestionConfigurationStatus.IN_PROGRESS
            config.number_of_questions_pending = total_questions
            config.number_of_questions_in_progress = 0
            config.number_of_questions_completed = 0
            config.number_of_questions_failed = 0
            config.save()
            logger.info(f"[CONFIG {config_uuid}] Status updated to IN_PROGRESS")
            logger.info(f"[CONFIG {config_uuid}] Pending: {config.number_of_questions_pending}, "
                       f"In Progress: {config.number_of_questions_in_progress}, "
                       f"Completed: {config.number_of_questions_completed}, "
                       f"Failed: {config.number_of_questions_failed}")
            
            category = Category.objects.get(uuid=category_uuid)
            topic = Topic.objects.get(uuid=topic_uuid)
            logger.info(f"[CONFIG {config_uuid}] Category: {category.name}, Topic: {topic.name}")
            subtopic = None
            
            if subtopic_uuid:
                subtopic = Subtopic.objects.get(uuid=subtopic_uuid)
                logger.info(f"[CONFIG {config_uuid}] Using existing subtopic: {subtopic.name}")
            else:
                logger.info(f"[CONFIG {config_uuid}] Subtopic not provided, generating one using AI for {category.name} > {topic.name}")
                subtopic_name = self.ollama_service.generate_subtopic_name(
                    category_name=category.name,
                    topic_name=topic.name,
                    topic_description=topic.description
                )
                
                if subtopic_name:
                    logger.info(f"[CONFIG {config_uuid}] Generated subtopic name: {subtopic_name}")
                    similar_subtopic_result = self._find_similar_subtopic(
                        subtopic_name=subtopic_name,
                        topic=topic
                    )
                    
                    if similar_subtopic_result:
                        subtopic, similarity_ratio = similar_subtopic_result
                        logger.info(
                            f"[CONFIG {config_uuid}] Using existing similar subtopic: '{subtopic.name}' "
                            f"(similarity: {similarity_ratio:.2f}) for generated name: '{subtopic_name}'"
                        )
                    else:
                        subtopic = Subtopic.objects.create(
                            name=subtopic_name,
                            description=f"Auto-generated subtopic for {topic.name}",
                            topic=topic,
                            created_by=user,
                            updated_by=user
                        )
                        logger.info(f"[CONFIG {config_uuid}] Created new subtopic: {subtopic_name} (UUID: {subtopic.uuid})")
                    
                    with transaction.atomic():
                        config.refresh_from_db()
                        config.subtopic = subtopic
                        config.name = f"{category.name} > {topic.name} > {subtopic.name} ({config.number_of_questions_to_generate} questions)"
                        config.save()
                        logger.info(f"[CONFIG {config_uuid}] Updated config with subtopic and new name")
                else:
                    logger.warning(f"[CONFIG {config_uuid}] Failed to generate subtopic name using AI, proceeding without subtopic")
            
            easy_count = int((difficulty_partitions['easy'] / 100) * total_questions)
            medium_count = int((difficulty_partitions['medium'] / 100) * total_questions)
            hard_count = total_questions - easy_count - medium_count
            
            logger.info(
                f"[CONFIG {config_uuid}] Generating {total_questions} questions: "
                f"{easy_count} easy, {medium_count} medium, {hard_count} hard"
            )
            
            batch_size = 10
            all_questions = []
            
            if easy_count > 0:
                logger.info(f"[CONFIG {config_uuid}] Starting EASY questions generation ({easy_count} questions)")
                easy_questions = self._generate_difficulty_batch(
                    category, topic, subtopic, DifficultyLevel.EASY,
                    easy_count, batch_size, user, config
                )
                all_questions.extend(easy_questions)
                logger.info(f"[CONFIG {config_uuid}] Completed EASY questions: {len(easy_questions)}/{easy_count}")
            
            if medium_count > 0:
                logger.info(f"[CONFIG {config_uuid}] Starting MEDIUM questions generation ({medium_count} questions)")
                medium_questions = self._generate_difficulty_batch(
                    category, topic, subtopic, DifficultyLevel.MEDIUM,
                    medium_count, batch_size, user, config
                )
                all_questions.extend(medium_questions)
                logger.info(f"[CONFIG {config_uuid}] Completed MEDIUM questions: {len(medium_questions)}/{medium_count}")
            
            if hard_count > 0:
                logger.info(f"[CONFIG {config_uuid}] Starting HARD questions generation ({hard_count} questions)")
                hard_questions = self._generate_difficulty_batch(
                    category, topic, subtopic, DifficultyLevel.HARD,
                    hard_count, batch_size, user, config
                )
                all_questions.extend(hard_questions)
                logger.info(f"[CONFIG {config_uuid}] Completed HARD questions: {len(hard_questions)}/{hard_count}")
            
            elapsed_time = int(time.time() - start_time)
            logger.info(f"[CONFIG {config_uuid}] Finalizing: Generated {len(all_questions)}/{total_questions} questions in {elapsed_time} seconds")
            
            with transaction.atomic():
                config.refresh_from_db()
                config.status = QuestionConfigurationStatus.COMPLETED
                config.number_of_questions_completed = len(all_questions)
                config.number_of_questions_failed = total_questions - len(all_questions)
                config.number_of_questions_pending = 0
                config.number_of_questions_in_progress = 0
                config.time_taken_in_seconds = elapsed_time
                config.save()
                logger.info(f"[CONFIG {config_uuid}] Status updated to COMPLETED")
                logger.info(f"[CONFIG {config_uuid}] Final counts - Completed: {config.number_of_questions_completed}, "
                           f"Failed: {config.number_of_questions_failed}, "
                           f"In Progress: {config.number_of_questions_in_progress}, "
                           f"Pending: {config.number_of_questions_pending}")
            
            logger.info(f"[CONFIG {config_uuid}] ========== QUESTION GENERATION COMPLETED ==========")
            
        except Exception as e:
            logger.error(f"[CONFIG {config_uuid}] ========== ERROR IN QUESTION GENERATION ==========")
            logger.error(f"[CONFIG {config_uuid}] Error: {str(e)}", exc_info=True)
            try:
                config = QuestionConfiguration.objects.get(uuid=config_uuid)
                config.refresh_from_db()
                logger.error(f"[CONFIG {config_uuid}] Current status before failure: {config.status}")
                logger.error(f"[CONFIG {config_uuid}] Current counts - Completed: {config.number_of_questions_completed}, "
                           f"Failed: {config.number_of_questions_failed}, "
                           f"In Progress: {config.number_of_questions_in_progress}, "
                           f"Pending: {config.number_of_questions_pending}")
                config.status = QuestionConfigurationStatus.FAILED
                config.save()
                logger.error(f"[CONFIG {config_uuid}] Status updated to FAILED")
            except Exception as save_error:
                logger.error(f"[CONFIG {config_uuid}] Failed to update config status: {str(save_error)}")
    
    def _generate_difficulty_batch(
        self,
        category: Category,
        topic: Topic,
        subtopic: Optional[Subtopic],
        difficulty: str,
        count: int,
        batch_size: int,
        user: User,
        config: QuestionConfiguration
    ) -> list:
        config_uuid = str(config.uuid)
        generated_questions = []
        
        context = f"Category: {category.name}, Topic: {topic.name}"
        if subtopic:
            context += f", Subtopic: {subtopic.name}"
        
        total_batches = (count + batch_size - 1) // batch_size
        logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Starting batch generation: {count} questions in {total_batches} batch(es)")
        
        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            batch_count = batch_end - batch_start
            batch_num = batch_start//batch_size + 1
            
            logger.info(
                f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}/{total_batches}: "
                f"Generating {batch_count} questions (range: {batch_start+1}-{batch_end})"
            )
            
            with transaction.atomic():
                config.refresh_from_db()
                old_pending = config.number_of_questions_pending
                old_in_progress = config.number_of_questions_in_progress
                config.number_of_questions_in_progress = batch_count
                config.number_of_questions_pending = (
                    config.number_of_questions_pending - batch_count
                )
                config.save()
                logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Updated status - "
                           f"Pending: {old_pending} -> {config.number_of_questions_pending}, "
                           f"In Progress: {old_in_progress} -> {config.number_of_questions_in_progress}")
            
            questions_needed = batch_count
            max_ollama_calls = batch_count * 3  
            ollama_call_count = 0
            processed_questions = 0
            duplicate_count = 0
            
            while processed_questions < questions_needed and ollama_call_count < max_ollama_calls:
                questions_to_generate = questions_needed - processed_questions
                ollama_call_count += 1
                logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Generating {questions_to_generate} question(s) (Ollama call {ollama_call_count}/{max_ollama_calls})")
                
                try:
                    ollama_questions = self.ollama_service.generate_questions_batch(
                        category_name=category.name,
                        topic_name=topic.name,
                        subtopic_name=subtopic.name if subtopic else None,
                        difficulty=difficulty,
                        count=questions_to_generate,
                        context=context
                    )
                    logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Ollama returned {len(ollama_questions)} question(s)")
                except Exception as ollama_error:
                    logger.error(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Ollama service error: {str(ollama_error)}", exc_info=True)
                    ollama_questions = []
                    # Mark failed questions
                    failed_count = questions_to_generate
                    with transaction.atomic():
                        config.refresh_from_db()
                        config.number_of_questions_failed += failed_count
                        config.number_of_questions_in_progress -= failed_count
                        config.save()
                    logger.error(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Marked {failed_count} questions as failed due to Ollama error")
                    break
                
                for ollama_q in ollama_questions:
                    try:
                        question_text = ollama_q.get('question', '')
                        if not question_text:
                            logger.warning(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Empty question text, skipping")
                            with transaction.atomic():
                                config.refresh_from_db()
                                config.number_of_questions_failed += 1
                                config.number_of_questions_in_progress -= 1
                                config.save()
                            continue
                        
                        similar_question = self._find_similar_question(
                            question_text=question_text,
                            category=category,
                            topic=topic,
                            subtopic=subtopic
                        )
                        
                        if similar_question:
                            duplicate_count += 1
                            logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Duplicate question detected (similarity >= {self.question_similarity_threshold})")
                            logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Similar question UUID: {similar_question.uuid}, Question: '{question_text[:80]}...'")
                            logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Skipping duplicate, will generate replacement in next iteration")
                            continue
                        
                        question = self._create_question_from_ollama(
                            ollama_q, category, topic, subtopic,
                            difficulty, user
                        )
                        
                        if question:
                            generated_questions.append(question)
                            processed_questions += 1
                            logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Question {processed_questions}/{questions_needed} created successfully (UUID: {question.uuid})")
                            
                            with transaction.atomic():
                                config.refresh_from_db()
                                old_completed = config.number_of_questions_completed
                                old_in_progress = config.number_of_questions_in_progress
                                config.number_of_questions_completed += 1
                                config.number_of_questions_in_progress -= 1
                                config.save()
                                logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Status updated - "
                                           f"Completed: {old_completed} -> {config.number_of_questions_completed}, "
                                           f"In Progress: {old_in_progress} -> {config.number_of_questions_in_progress}")
                        else:
                            logger.warning(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Question creation returned None (invalid data)")
                            with transaction.atomic():
                                config.refresh_from_db()
                                config.number_of_questions_failed += 1
                                config.number_of_questions_in_progress -= 1
                                config.save()
                    except Exception as e:
                        logger.error(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Error processing question: {str(e)}", exc_info=True)
                        with transaction.atomic():
                            config.refresh_from_db()
                            config.number_of_questions_failed += 1
                            config.number_of_questions_in_progress -= 1
                            config.save()
                
                if processed_questions < questions_needed:
                    remaining = questions_needed - processed_questions
                    logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Need {remaining} more question(s) (found {duplicate_count} duplicates so far), continuing generation...")
            
            if processed_questions < questions_needed:
                remaining = questions_needed - processed_questions
                logger.warning(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Could not generate all {questions_needed} questions. Generated {processed_questions}/{questions_needed} (found {duplicate_count} duplicates)")
                with transaction.atomic():
                    config.refresh_from_db()
                    config.number_of_questions_failed += remaining
                    config.number_of_questions_in_progress -= remaining
                    config.save()
            elif duplicate_count > 0:
                logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num}: Successfully generated all {questions_needed} questions (skipped {duplicate_count} duplicates)")
            
            logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] Batch {batch_num} completed: {len(generated_questions)} questions generated so far")
        
        logger.info(f"[CONFIG {config_uuid}] [{difficulty.upper()}] All batches completed: {len(generated_questions)}/{count} questions generated")
        return generated_questions
    
    def _find_similar_question(
        self,
        question_text: str,
        category: Category,
        topic: Topic,
        subtopic: Optional[Subtopic],
        threshold: float = None
    ) -> Optional[Question]:
        if threshold is None:
            threshold = self.question_similarity_threshold
        
        existing_questions = Question.objects.filter(
            category=category,
            topic=topic
        )
        
        if subtopic:
            existing_questions = existing_questions.filter(subtopic=subtopic)
        else:
            existing_questions = existing_questions.filter(subtopic__isnull=True)
        
        if not existing_questions.exists():
            return None
        
        normalized_question_text = question_text.lower().strip()
        best_match = None
        best_ratio = 0.0
        
        for existing_q in existing_questions:
            normalized_existing_text = existing_q.question.lower().strip()
            ratio = difflib.SequenceMatcher(
                None,
                normalized_question_text,
                normalized_existing_text
            ).ratio()
            
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = existing_q
        
        if best_match:
            logger.info(
                f"Found similar question (similarity: {best_ratio:.2f}): "
                f"'{best_match.question[:50]}...'"
            )
            return best_match
        
        return None
    
    def _create_question_from_ollama(
        self,
        ollama_data: Dict,
        category: Category,
        topic: Topic,
        subtopic: Optional[Subtopic],
        difficulty: str,
        user: User
    ) -> Optional[Question]:
        try:
            question_text = ollama_data.get('question', '')
            if not question_text:
                logger.warning("Empty question text, skipping question creation")
                return None
            
            similar_question = self._find_similar_question(
                question_text=question_text,
                category=category,
                topic=topic,
                subtopic=subtopic
            )
            
            if similar_question:
                logger.info(
                    f"Skipping duplicate question. Similar question found: "
                    f"UUID={similar_question.uuid}, similarity >= {self.question_similarity_threshold}"
                )
                return None
            
            weightages = self.weightage_calculator.calculate_weightages(
                question=question_text,
                expected_answer=ollama_data.get('expected_answer', ''),
                keywords=ollama_data.get('keywords', []),
                difficulty=difficulty
            )
            
            keywords_coverage = self.weightage_calculator.calculate_keywords_coverage(
                keywords=ollama_data.get('keywords', []),
                expected_answer=ollama_data.get('expected_answer', '')
            )
            
            question_name = f"{topic.name}"
            if subtopic:
                question_name += f" - {subtopic.name}"
            question_name += f" ({difficulty.upper()})"
            
            question = Question.objects.create(
                name=question_name,
                description=f"Auto-generated question for {category.name} > {topic.name}",
                category=category,
                topic=topic,
                subtopic=subtopic,
                question=question_text,
                difficulty_level=difficulty,
                expected_answer=ollama_data.get('expected_answer', ''),
                expected_time_in_seconds=ollama_data.get('time_in_seconds', 120),
                ideal_answer_summary=ollama_data.get('ideal_answer_summary', ''),
                red_flags=ollama_data.get('red_flags', []),
                expected_keywords=ollama_data.get('keywords', []),
                expected_keywords_coverage=keywords_coverage,
                created_by=user,
                updated_by=user,
                **weightages
            )
            
            return question
            
        except Exception as e:
            logger.error(f"Error creating question from Ollama data: {str(e)}", exc_info=True)
            return None

