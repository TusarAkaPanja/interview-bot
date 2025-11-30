# Interview Panel API Documentation

## Overview

The Interview Panel API provides endpoints for managing interview panels, including creating panels, assigning candidates, and configuring question distributions based on categories, topics, subtopics, and difficulty levels.

**Base URL:** `/api/panel/`

**Authentication:** All endpoints require authentication. Users must be authenticated and have Admin or HR role.

---

## Endpoints

### 1. Create Interview Panel

Create a new interview panel with question distributions and candidate assignments.

**Endpoint:** `POST /api/panel/create/`

**Authentication:** Required (Admin or HR only)

**Request Body:**

```json
{
  "name": "Python Developer Interview - 2024",
  "description": "Technical interview for Python developer position",
  "total_number_of_questions": 10,
  "start_datetime": "2024-12-01T09:00:00Z",
  "end_datetime": "2024-12-01T18:00:00Z",
  "category_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "question_distributions": [
    {
      "topic_uuid": "123e4567-e89b-12d3-a456-426614174001",
      "subtopic_uuid": "123e4567-e89b-12d3-a456-426614174002",
      "easy": 2,
      "medium": 3,
      "hard": 1
    },
    {
      "topic_uuid": "123e4567-e89b-12d3-a456-426614174003",
      "subtopic_uuid": "123e4567-e89b-12d3-a456-426614174004",
      "easy": 1,
      "medium": 2,
      "hard": 1
    }
  ],
  "candidate_uuids": [
    "123e4567-e89b-12d3-a456-426614174005",
    "123e4567-e89b-12d3-a456-426614174006"
  ]
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Name of the interview panel (max 255 characters) |
| `description` | string | No | Description of the interview panel |
| `total_number_of_questions` | integer | Yes | Total number of questions (min: 1) |
| `start_datetime` | datetime | Yes | Start date and time of the interview panel (ISO 8601 format) |
| `end_datetime` | datetime | Yes | End date and time of the interview panel (ISO 8601 format) |
| `category_uuid` | UUID | Yes | UUID of the question category |
| `question_distributions` | array | Yes | Array of question distribution objects |
| `candidate_uuids` | array | No | Array of candidate UUIDs to assign to the panel |

**Question Distribution Object:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic_uuid` | UUID | Yes | UUID of the topic |
| `subtopic_uuid` | UUID | Yes | UUID of the subtopic |
| `easy` | integer | Yes | Number of easy questions (min: 0) |
| `medium` | integer | Yes | Number of medium questions (min: 0) |
| `hard` | integer | Yes | Number of hard questions (min: 0) |

**Validation Rules:**

- `end_datetime` must be after `start_datetime`
- Sum of all question distributions (easy + medium + hard) must equal `total_number_of_questions`
- At least one question count (easy, medium, or hard) must be greater than 0 in each distribution
- Category, topics, and subtopics must exist and be valid
- Candidates must belong to the same organization as the user

**Response (201 Created):**

```json
{
  "success": true,
  "message": "Interview panel created successfully",
  "data": {
    "uuid": "123e4567-e89b-12d3-a456-426614174007",
    "name": "Python Developer Interview - 2024",
    "description": "Technical interview for Python developer position",
    "total_number_of_questions": 10,
    "start_datetime": "2024-12-01T09:00:00Z",
    "end_datetime": "2024-12-01T18:00:00Z",
    "is_active": true,
    "organization": "123e4567-e89b-12d3-a456-426614174008",
    "created_at": "2024-11-30T10:00:00Z",
    "updated_at": "2024-11-30T10:00:00Z",
    "question_distributions": [
      {
        "uuid": "123e4567-e89b-12d3-a456-426614174009",
        "category": "Python",
        "topic": "Data Structures",
        "subtopic": "Lists",
        "easy": 2,
        "medium": 3,
        "hard": 1,
        "total": 6
      }
    ],
    "candidates": [
      {
        "uuid": "123e4567-e89b-12d3-a456-426614174010",
        "candidate_uuid": "123e4567-e89b-12d3-a456-426614174005",
        "candidate_name": "John Doe",
        "candidate_email": "john.doe@example.com",
        "token": "abc123def456ghi789jkl012mno345pq",
        "token_expires_at": "2024-12-01T18:00:00Z",
        "score": 0
      }
    ]
  }
}
```

**Error Responses:**

- `400 Bad Request`: Invalid request data or validation errors
- `403 Forbidden`: User is not Admin or HR
- `404 Not Found`: Category, topic, subtopic, or candidate not found

---

### 2. Get All Interview Panels

Retrieve all interview panels for the authenticated user's organization.

**Endpoint:** `GET /api/panel/get/`

**Authentication:** Required

**Query Parameters:** None

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Interview panels retrieved successfully",
  "data": {
    "interview_panels": [
      {
        "uuid": "123e4567-e89b-12d3-a456-426614174007",
        "name": "Python Developer Interview - 2024",
        "description": "Technical interview for Python developer position",
        "total_number_of_questions": 10,
        "start_datetime": "2024-12-01T09:00:00Z",
        "end_datetime": "2024-12-01T18:00:00Z",
        "is_active": true,
        "organization": "123e4567-e89b-12d3-a456-426614174008",
        "created_at": "2024-11-30T10:00:00Z",
        "updated_at": "2024-11-30T10:00:00Z",
        "question_distributions": [...],
        "candidates": [...]
      }
    ]
  }
}
```

**Error Responses:**

- `403 Forbidden`: User must belong to an organization

**Note:** Panels are automatically deactivated if `end_datetime` has passed. Results are ordered by creation date (newest first).

---

### 3. Get Single Interview Panel

Retrieve a specific interview panel by UUID.

**Endpoint:** `GET /api/panel/get/<interview_panel_uuid>/`

**Authentication:** Required

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `interview_panel_uuid` | UUID | UUID of the interview panel |

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Interview panel retrieved successfully",
  "data": {
    "uuid": "123e4567-e89b-12d3-a456-426614174007",
    "name": "Python Developer Interview - 2024",
    "description": "Technical interview for Python developer position",
    "total_number_of_questions": 10,
    "start_datetime": "2024-12-01T09:00:00Z",
    "end_datetime": "2024-12-01T18:00:00Z",
    "is_active": true,
    "organization": "123e4567-e89b-12d3-a456-426614174008",
    "created_at": "2024-11-30T10:00:00Z",
    "updated_at": "2024-11-30T10:00:00Z",
    "question_distributions": [...],
    "candidates": [...]
  }
}
```

**Error Responses:**

- `403 Forbidden`: User must belong to an organization
- `404 Not Found`: Interview panel not found or doesn't belong to user's organization

---

### 4. Update Interview Panel

Update an existing interview panel. Only active panels can be updated.

**Endpoint:** `PUT /api/panel/update/<interview_panel_uuid>/`

**Authentication:** Required (Admin or HR only)

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `interview_panel_uuid` | UUID | UUID of the interview panel to update |

**Request Body:**

All fields are optional (partial update supported):

```json
{
  "name": "Updated Interview Panel Name",
  "description": "Updated description",
  "start_datetime": "2024-12-02T09:00:00Z",
  "end_datetime": "2024-12-02T18:00:00Z"
}
```

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Name of the interview panel (max 255 characters) |
| `description` | string | No | Description of the interview panel |
| `start_datetime` | datetime | No | Start date and time (ISO 8601 format) |
| `end_datetime` | datetime | No | End date and time (ISO 8601 format) |

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Interview panel updated successfully",
  "data": {
    "uuid": "123e4567-e89b-12d3-a456-426614174007",
    "name": "Updated Interview Panel Name",
    "description": "Updated description",
    "total_number_of_questions": 10,
    "start_datetime": "2024-12-02T09:00:00Z",
    "end_datetime": "2024-12-02T18:00:00Z",
    "is_active": true,
    "organization": "123e4567-e89b-12d3-a456-426614174008",
    "created_at": "2024-11-30T10:00:00Z",
    "updated_at": "2024-12-01T11:00:00Z",
    "question_distributions": [...],
    "candidates": [...]
  }
}
```

**Error Responses:**

- `400 Bad Request`: Invalid request data, validation errors, or panel is inactive
- `403 Forbidden`: User is not Admin or HR, or user must have a role
- `404 Not Found`: Interview panel not found

**Note:** Inactive panels (where `end_datetime` has passed) cannot be updated.

---

### 5. Delete Interview Panel

Soft delete an interview panel (marks as deleted, doesn't remove from database).

**Endpoint:** `DELETE /api/panel/delete/<interview_panel_uuid>/`

**Authentication:** Required (Admin or HR only)

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `interview_panel_uuid` | UUID | UUID of the interview panel to delete |

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Interview panel deleted successfully"
}
```

**Error Responses:**

- `400 Bad Request`: Interview panel UUID is required
- `403 Forbidden`: User is not Admin or HR, or user must have a role
- `404 Not Found`: Interview panel not found

---

## Response Data Structures

### Interview Panel Object

```json
{
  "uuid": "string (UUID)",
  "name": "string",
  "description": "string",
  "total_number_of_questions": "integer",
  "start_datetime": "datetime (ISO 8601)",
  "end_datetime": "datetime (ISO 8601)",
  "is_active": "boolean",
  "organization": "string (UUID)",
  "created_at": "datetime (ISO 8601)",
  "updated_at": "datetime (ISO 8601)",
  "question_distributions": "array of QuestionDistribution objects",
  "candidates": "array of Candidate objects"
}
```

### Question Distribution Object

```json
{
  "uuid": "string (UUID)",
  "category": "string",
  "topic": "string",
  "subtopic": "string",
  "easy": "integer",
  "medium": "integer",
  "hard": "integer",
  "total": "integer"
}
```

### Candidate Object

```json
{
  "uuid": "string (UUID)",
  "candidate_uuid": "string (UUID)",
  "candidate_name": "string",
  "candidate_email": "string",
  "token": "string",
  "token_expires_at": "datetime (ISO 8601)",
  "score": "integer"
}
```

---

## Common Error Responses

All endpoints follow a consistent error response format:

```json
{
  "success": false,
  "message": "Error message",
  "errors": {
    "field_name": ["Error detail 1", "Error detail 2"]
  }
}
```

**Common HTTP Status Codes:**

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data or validation errors
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

---

## Notes

1. **Authentication**: All endpoints require a valid authentication token. Include the token in the `Authorization` header.

2. **Permissions**: Create, update, and delete operations require Admin or HR role.

3. **Organization Scope**: Users can only access interview panels belonging to their organization.

4. **Auto-deactivation**: Interview panels are automatically deactivated when `end_datetime` has passed. Inactive panels cannot be updated.

5. **Soft Delete**: Delete operations perform soft deletes (sets `is_deleted=True`). Deleted panels are excluded from GET requests.

6. **Candidate Tokens**: When candidates are assigned to a panel, unique tokens are automatically generated for each candidate. These tokens expire when the panel's `end_datetime` is reached.

7. **Question Distribution Validation**: The sum of all question distributions must exactly match the `total_number_of_questions` specified in the panel.

---

## Example Usage

### Create an Interview Panel

```bash
curl -X POST http://localhost:8000/api/panel/create/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Python Developer Interview",
    "description": "Technical assessment",
    "total_number_of_questions": 10,
    "start_datetime": "2024-12-01T09:00:00Z",
    "end_datetime": "2024-12-01T18:00:00Z",
    "category_uuid": "123e4567-e89b-12d3-a456-426614174000",
    "question_distributions": [
      {
        "topic_uuid": "123e4567-e89b-12d3-a456-426614174001",
        "subtopic_uuid": "123e4567-e89b-12d3-a456-426614174002",
        "easy": 3,
        "medium": 4,
        "hard": 3
      }
    ],
    "candidate_uuids": ["123e4567-e89b-12d3-a456-426614174005"]
  }'
```

### Get All Interview Panels

```bash
curl -X GET http://localhost:8000/api/panel/get/ \
  -H "Authorization: Bearer <token>"
```

### Get Single Interview Panel

```bash
curl -X GET http://localhost:8000/api/panel/get/123e4567-e89b-12d3-a456-426614174007/ \
  -H "Authorization: Bearer <token>"
```

### Update Interview Panel

```bash
curl -X PUT http://localhost:8000/api/panel/update/123e4567-e89b-12d3-a456-426614174007/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Panel Name",
    "end_datetime": "2024-12-02T18:00:00Z"
  }'
```

### Delete Interview Panel

```bash
curl -X DELETE http://localhost:8000/api/panel/delete/123e4567-e89b-12d3-a456-426614174007/ \
  -H "Authorization: Bearer <token>"
```

