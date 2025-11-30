# Authentication API Documentation

## Overview

The Authentication API provides endpoints for user authentication, registration, and candidate management using JWT tokens.

**Base URL:** `/api/auth/`

**Authentication:** Most endpoints require JWT authentication. Include the access token in the Authorization header: `Authorization: Bearer <access_token>`

---

## Endpoints

### 1. User Login

Authenticate a user and receive JWT access and refresh tokens.

**Endpoint:** `POST /api/auth/login/`

**Authentication:** Not required

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (200 OK):**
```json
{
  "message": "User logged in successfully",
  "status": "success",
  "data": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid credentials or missing fields
- `401 Unauthorized`: Invalid email or password

---

### 2. Refresh Token

Get a new access token using a refresh token.

**Endpoint:** `POST /api/auth/token/refresh/`

**Authentication:** Not required

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response (200 OK):**
```json
{
  "message": "Token refreshed successfully",
  "status": "success",
  "data": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid or expired refresh token

---

### 3. User Registration

Register a new admin user.

**Endpoint:** `POST /api/auth/register/`

**Authentication:** Not required

**Request Body:**
```json
{
  "email": "admin@example.com",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response (201 Created):**
```json
{
  "message": "User registered successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "email": "admin@example.com",
    "role": {
      "id": 1,
      "uuid": "123e4567-e89b-12d3-a456-426614174001",
      "name": "admin"
    },
    "role_uuid": "123e4567-e89b-12d3-a456-426614174001",
    "is_active": true,
    "created_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Validation errors (e.g., email already exists, password too short)

---

### 4. Register Candidate

Register a new candidate. Only Admin or HR users can register candidates.

**Endpoint:** `POST /api/auth/register/candidate/`

**Authentication:** Required (Admin or HR only)

**Request Body:**
```json
{
  "email": "candidate@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "password": "optionalpassword123"
}
```

**Note:** If password is not provided, a random password will be generated.

**Response (201 Created):**
```json
{
  "message": "Candidate registered successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174002",
    "email": "candidate@example.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "created_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: User must belong to an organization
- `403 Forbidden`: Only admin or HR can register candidates
- `400 Bad Request`: Validation errors

---

### 5. Get Candidates

Retrieve all candidates belonging to the authenticated user's organization.

**Endpoint:** `GET /api/auth/candidates/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "Candidates fetched successfully",
  "status": "success",
  "data": [
    {
      "id": 1,
      "uuid": "123e4567-e89b-12d3-a456-426614174002",
      "email": "candidate@example.com",
      "first_name": "Jane",
      "last_name": "Smith",
      "created_at": "2024-12-01T10:00:00Z"
    }
  ]
}
```

**Error Responses:**
- `400 Bad Request`: User must belong to an organization
- `401 Unauthorized`: Invalid or missing authentication token

---

### 6. User Logout

Logout the authenticated user and clear cookies.

**Endpoint:** `POST /api/auth/logout/`

**Authentication:** Required

**Response (200 OK):**
```json
{
  "message": "User logged out successfully",
  "status": "success"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid or missing authentication token

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

Most endpoints require JWT authentication. Include the access token in the request header:

```
Authorization: Bearer <access_token>
```

Access tokens expire after a set period. Use the refresh token endpoint to obtain a new access token.

---

## Notes

- Password must be at least 8 characters long for user registration
- New users are automatically assigned the "admin" role
- Candidates are automatically associated with the registering user's organization
- All timestamps are in ISO 8601 format (UTC)

