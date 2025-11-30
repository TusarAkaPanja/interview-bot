# Question Bank API Documentation

## Overview

The Question Bank API provides endpoints for managing categories, topics, subtopics, and questions. It also supports AI-powered question generation using Ollama. The API follows a hierarchical structure: Categories → Topics → Subtopics → Questions.

**Base URL:** `/api/questionbank/`

**Authentication:** All endpoints require JWT authentication. Include the access token in the Authorization header: `Authorization: Bearer <access_token>`

---

## Table of Contents

1. [Category Endpoints](#category-endpoints)
2. [Topic Endpoints](#topic-endpoints)
3. [Subtopic Endpoints](#subtopic-endpoints)
4. [Question Endpoints](#question-endpoints)
5. [Question Generation Endpoints](#question-generation-endpoints)

---

## Category Endpoints

### 1. Create Category

Create a new category for organizing questions.

**Endpoint:** `POST /api/questionbank/create-category/`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Programming Languages",
  "description": "Questions related to various programming languages"
}
```

**Response (201 Created):**
```json
{
  "message": "Category created successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Programming Languages",
    "description": "Questions related to various programming languages",
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Validation errors (e.g., category name already exists)
- `401 Unauthorized`: Invalid or missing authentication token

**Usage:** Categories are top-level organizational units. Each category must have a unique name.

---

### 2. Get All Categories

Retrieve all available categories.

**Endpoint:** `GET /api/questionbank/get-categories/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "Categories retrieved successfully",
  "status": "success",
  "data": [
    {
      "id": 1,
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Programming Languages",
      "description": "Questions related to various programming languages",
      "created_at": "2024-12-01T10:00:00Z",
      "updated_at": "2024-12-01T10:00:00Z"
    }
  ]
}
```

---

### 3. Get Category by UUID

Retrieve a specific category by its UUID.

**Endpoint:** `GET /api/questionbank/get-category/<category_uuid>/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "Category retrieved successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Programming Languages",
    "description": "Questions related to various programming languages",
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found`: Category not found

---

### 4. Update Category

Update an existing category.

**Endpoint:** `PUT /api/questionbank/update-category/<category_uuid>/`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Updated Category Name",
  "description": "Updated description"
}
```

**Response (200 OK):**
```json
{
  "message": "Category updated successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Updated Category Name",
    "description": "Updated description",
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T11:00:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found`: Category not found
- `400 Bad Request`: Validation errors

---

## Topic Endpoints

### 1. Create Topic

Create a new topic under a category.

**Endpoint:** `POST /api/questionbank/create-topic/`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Python",
  "description": "Python programming language questions",
  "category_uuid": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Response (201 Created):**
```json
{
  "message": "Topic created successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174001",
    "name": "Python",
    "description": "Python programming language questions",
    "category": 1,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Validation errors (e.g., topic name already exists in category, category not found)
- `401 Unauthorized`: Invalid or missing authentication token

**Usage:** Topics belong to categories. Each topic name must be unique within its category.

---

### 2. Get Topic by UUID

Retrieve a specific topic by its UUID.

**Endpoint:** `GET /api/questionbank/get-topic/<topic_uuid>/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "Topic retrieved successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174001",
    "name": "Python",
    "description": "Python programming language questions",
    "category": 1,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found`: Topic not found

---

### 3. Get Topics by Category

Retrieve all topics belonging to a specific category.

**Endpoint:** `GET /api/questionbank/get-topics-by-category/<category_uuid>/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "2 topics retrieved successfully for category 123e4567-e89b-12d3-a456-426614174000",
  "status": "success",
  "data": [
    {
      "id": 1,
      "uuid": "123e4567-e89b-12d3-a456-426614174001",
      "name": "Python",
      "description": "Python programming language questions",
      "category": 1,
      "created_at": "2024-12-01T10:00:00Z",
      "updated_at": "2024-12-01T10:00:00Z"
    }
  ]
}
```

---

### 4. Update Topic

Update an existing topic.

**Endpoint:** `PUT /api/questionbank/update-topic/<topic_uuid>/`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Updated Topic Name",
  "description": "Updated description",
  "category_uuid": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Response (200 OK):**
```json
{
  "message": "Topic updated successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174001",
    "name": "Updated Topic Name",
    "description": "Updated description",
    "category": 1,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T11:00:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found`: Topic not found
- `400 Bad Request`: Validation errors

---

## Subtopic Endpoints

### 1. Create Subtopic

Create a new subtopic under a topic.

**Endpoint:** `POST /api/questionbank/create-subtopic/`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Django Framework",
  "description": "Django web framework questions",
  "topic_uuid": "123e4567-e89b-12d3-a456-426614174001"
}
```

**Response (201 Created):**
```json
{
  "message": "Subtopic created successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174002",
    "name": "Django Framework",
    "description": "Django web framework questions",
    "topic": 1,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Validation errors (e.g., subtopic name already exists in topic, topic not found)
- `401 Unauthorized`: Invalid or missing authentication token

**Usage:** Subtopics belong to topics. Each subtopic name must be unique within its topic. Subtopics are optional for questions.

---

### 2. Get Subtopic by UUID

Retrieve a specific subtopic by its UUID.

**Endpoint:** `GET /api/questionbank/get-subtopic/<subtopic_uuid>/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "Subtopic retrieved successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174002",
    "name": "Django Framework",
    "description": "Django web framework questions",
    "topic": 1,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found`: Subtopic not found

---

### 3. Get Subtopics by Topic

Retrieve all subtopics belonging to a specific topic.

**Endpoint:** `GET /api/questionbank/get-subtopics-by-topic/<topic_uuid>/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "2 subtopics retrieved successfully for topic 123e4567-e89b-12d3-a456-426614174001",
  "status": "success",
  "data": [
    {
      "id": 1,
      "uuid": "123e4567-e89b-12d3-a456-426614174002",
      "name": "Django Framework",
      "description": "Django web framework questions",
      "topic": 1,
      "created_at": "2024-12-01T10:00:00Z",
      "updated_at": "2024-12-01T10:00:00Z"
    }
  ]
}
```

---

### 4. Update Subtopic

Update an existing subtopic.

**Endpoint:** `PUT /api/questionbank/update-subtopic/<subtopic_uuid>/`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Updated Subtopic Name",
  "description": "Updated description",
  "topic_uuid": "123e4567-e89b-12d3-a456-426614174001"
}
```

**Response (200 OK):**
```json
{
  "message": "Subtopic updated successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174002",
    "name": "Updated Subtopic Name",
    "description": "Updated description",
    "topic": 1,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T11:00:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found`: Subtopic not found
- `400 Bad Request`: Validation errors

---

## Question Endpoints

### 1. Create Question

Create a new question manually. Only Admin or Superadmin can create questions.

**Endpoint:** `POST /api/questionbank/create-question/`

**Authentication:** Required (Admin or Superadmin only)

**Request Body:**
```json
{
  "name": "Python List Comprehension",
  "description": "Question about Python list comprehensions",
  "category_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "topic_uuid": "123e4567-e89b-12d3-a456-426614174001",
  "subtopic_uuid": null,
  "question": "Explain how list comprehensions work in Python with examples.",
  "difficulty_level": "medium",
  "expected_answer": "List comprehensions provide a concise way to create lists...",
  "expected_time_in_seconds": 120,
  "ideal_answer_summary": "Should cover syntax, examples, and use cases",
  "red_flags": ["No examples provided", "Incorrect syntax"],
  "expected_keywords": ["list comprehension", "syntax", "example"],
  "expected_keywords_coverage": 0.8,
  "score_weight_technical": 0.6,
  "score_weight_domain_knowledge": 0.3,
  "score_weight_communication": 0.1
}
```

**Response (201 Created):**
```json
{
  "message": "Question created successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174003",
    "name": "Python List Comprehension",
    "description": "Question about Python list comprehensions",
    "category": 1,
    "topic": 1,
    "subtopic": null,
    "question": "Explain how list comprehensions work in Python with examples.",
    "difficulty_level": "medium",
    "expected_answer": "List comprehensions provide a concise way to create lists...",
    "expected_time_in_seconds": 120,
    "ideal_answer_summary": "Should cover syntax, examples, and use cases",
    "red_flags": ["No examples provided", "Incorrect syntax"],
    "expected_keywords": ["list comprehension", "syntax", "example"],
    "expected_keywords_coverage": 0.8,
    "score_weight_technical": 0.6,
    "score_weight_domain_knowledge": 0.3,
    "score_weight_communication": 0.1,
    "score_weight_problem_solving": 0.05,
    "score_weight_creativity": 0.05,
    "score_weight_attention_to_detail": 0.05,
    "score_weight_time_management": 0.05,
    "score_weight_stress_management": 0.05,
    "score_weight_adaptability": 0.05,
    "score_weight_confidence": 0.05,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `403 Forbidden`: Only admin and superadmin can create questions
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Invalid or missing authentication token

**Usage:** Questions can be created manually or generated automatically. All score weights should sum to approximately 1.0.

---

### 2. Get Question by UUID

Retrieve a specific question by its UUID.

**Endpoint:** `GET /api/questionbank/get-question/<question_uuid>/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "Question retrieved successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174003",
    "name": "Python List Comprehension",
    "question": "Explain how list comprehensions work in Python with examples.",
    "difficulty_level": "medium",
    "expected_answer": "List comprehensions provide a concise way to create lists...",
    "expected_time_in_seconds": 120,
    "category": 1,
    "topic": 1,
    "subtopic": null,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found`: Question not found

---

### 3. Get All Questions

Retrieve all questions with optional filtering, sorting, and pagination.

**Endpoint:** `GET /api/questionbank/get-all-questions/`

**Authentication:** Required

**Query Parameters:**
- `category_uuid` (optional): Filter by category UUID
- `topic_uuid` (optional): Filter by topic UUID
- `subtopic_uuid` (optional): Filter by subtopic UUID
- `difficulty_level` (optional): Filter by difficulty (easy, medium, hard)
- `search` (optional): Search in question text
- `sort` (optional): Field to sort by
- `order` (optional): Sort order (asc/desc)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 10, max: 100)

**Example Request:**
```
GET /api/questionbank/get-all-questions/?category_uuid=123e4567-e89b-12d3-a456-426614174000&difficulty_level=medium&page=1&page_size=20
```

**Response (200 OK):**
```json
{
  "count": 50,
  "next": "http://api.example.com/api/questionbank/get-all-questions/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "uuid": "123e4567-e89b-12d3-a456-426614174003",
      "name": "Python List Comprehension",
      "question": "Explain how list comprehensions work in Python with examples.",
      "difficulty_level": "medium",
      "category": 1,
      "topic": 1,
      "subtopic": null,
      "created_at": "2024-12-01T10:00:00Z"
    }
  ]
}
```

**Usage:** Use query parameters to filter and paginate results. The response follows Django REST Framework pagination format.

---

### 4. Update Question

Update an existing question. Only Admin or Superadmin can update questions.

**Endpoint:** `PUT /api/questionbank/update-question/<question_uuid>/`

**Authentication:** Required (Admin or Superadmin only)

**Request Body:**
```json
{
  "question": "Updated question text",
  "difficulty_level": "hard",
  "expected_answer": "Updated expected answer"
}
```

**Response (200 OK):**
```json
{
  "message": "Question updated successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174003",
    "name": "Python List Comprehension",
    "question": "Updated question text",
    "difficulty_level": "hard",
    "expected_answer": "Updated expected answer",
    "updated_at": "2024-12-01T11:00:00Z"
  }
}
```

**Error Responses:**
- `403 Forbidden`: Only admin and superadmin can update questions
- `404 Not Found`: Question not found
- `400 Bad Request`: Validation errors

---

## Question Generation Endpoints

### 1. Generate Questions

Generate questions automatically using AI (Ollama). Only Admin or HR users can generate questions.

**Endpoint:** `POST /api/questionbank/generate-questions/`

**Authentication:** Required (Admin or HR only)

**Request Body:**
```json
{
  "category_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "topic_uuid": "123e4567-e89b-12d3-a456-426614174001",
  "subtopic_uuid": "123e4567-e89b-12d3-a456-426614174002",
  "number_of_questions": 10,
  "difficulty_partitions": {
    "easy": 30,
    "medium": 50,
    "hard": 20
  }
}
```

**Note:** 
- `subtopic_uuid` is optional
- `difficulty_partitions` percentages must sum to 100
- Question generation runs asynchronously

**Response (202 Accepted):**
```json
{
  "message": "Question generation started successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174004",
    "name": "Programming Languages > Python > Django Framework (10 questions)",
    "organization": 1,
    "category": 1,
    "topic": 1,
    "subtopic": 1,
    "status": "pending",
    "number_of_questions_to_generate": 10,
    "number_of_questions_failed": 0,
    "number_of_questions_completed": 0,
    "number_of_questions_pending": 10,
    "number_of_questions_in_progress": 0,
    "time_taken_in_seconds": 0,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `403 Forbidden`: Only admin and HR users can generate questions
- `400 Bad Request`: Validation errors (e.g., difficulty partitions don't sum to 100, category/topic not found)
- `404 Not Found`: Category, topic, or subtopic not found

**Usage:** 
- Question generation is asynchronous. Use the configuration UUID to check status.
- The system will generate questions based on the difficulty distribution specified.
- Questions are generated using AI and may take time depending on the number requested.

---

### 2. Get Question Configuration Status

Check the status of a question generation job.

**Endpoint:** `GET /api/questionbank/question-configuration-status/<config_uuid>/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "Configuration status retrieved successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174004",
    "name": "Programming Languages > Python > Django Framework (10 questions)",
    "organization": 1,
    "category": 1,
    "topic": 1,
    "subtopic": 1,
    "status": "completed",
    "number_of_questions_to_generate": 10,
    "number_of_questions_failed": 0,
    "number_of_questions_completed": 10,
    "number_of_questions_pending": 0,
    "number_of_questions_in_progress": 0,
    "time_taken_in_seconds": 45,
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-01T10:05:00Z"
  }
}
```

**Status Values:**
- `pending`: Generation not started yet
- `in_progress`: Generation in progress
- `completed`: All questions generated successfully
- `failed`: Generation failed

**Error Responses:**
- `403 Forbidden`: You do not have access to this configuration (different organization)
- `404 Not Found`: Configuration not found

**Usage:** Poll this endpoint to check the progress of question generation. The status will update as questions are generated.

---

## Response Format

All API responses follow a consistent format:

**Success Response:**
```json
{
  "message": "Success message",
  "status": "success",
  "data": { ... }
}
```

**Error Response:**
```json
{
  "message": "Error message",
  "status": "error",
  "errors": "Detailed error information"
}
```

---

## Authentication

All endpoints require JWT authentication. Include the access token in the request header:

```
Authorization: Bearer <access_token>
```

---

## Notes

- **Hierarchical Structure:** Categories → Topics → Subtopics → Questions
- **Permissions:**
  - All authenticated users can view categories, topics, subtopics, and questions
  - Only Admin or Superadmin can create/update questions manually
  - Only Admin or HR can generate questions using AI
- **Question Generation:** Runs asynchronously. Use the configuration status endpoint to track progress.
- **Pagination:** The "Get All Questions" endpoint supports pagination with a default page size of 10 and maximum of 100.
- **Difficulty Levels:** Must be one of: `easy`, `medium`, `hard`
- **Score Weights:** All score weight fields should sum to approximately 1.0 for proper evaluation
- **Organization Isolation:** Question configurations are organization-specific. Users can only access configurations from their own organization.

---

## Common Use Cases

### 1. Setting Up Question Bank Structure

1. Create a category: `POST /api/questionbank/create-category/`
2. Create topics under the category: `POST /api/questionbank/create-topic/`
3. (Optional) Create subtopics under topics: `POST /api/questionbank/create-subtopic/`

### 2. Generating Questions

1. Generate questions: `POST /api/questionbank/generate-questions/`
2. Check status: `GET /api/questionbank/question-configuration-status/<config_uuid>/`
3. Retrieve generated questions: `GET /api/questionbank/get-all-questions/?category_uuid=...`

### 3. Filtering and Searching Questions

Use query parameters with `GET /api/questionbank/get-all-questions/`:
- Filter by category, topic, subtopic, or difficulty
- Search in question text
- Sort and paginate results

