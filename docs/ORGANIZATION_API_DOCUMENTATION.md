# Organization API Documentation

## Overview

The Organization API provides endpoints for creating organizations and managing HR users within organizations.

**Base URL:** `/api/organizations/`

**Authentication:** All endpoints require JWT authentication. Include the access token in the Authorization header: `Authorization: Bearer <access_token>`

---

## Endpoints

### 1. Create Organization

Create a new organization. The authenticated user will be assigned as the admin of the organization.

**Endpoint:** `POST /api/organizations/create/`

**Authentication:** Required

**Request Body:**
```json
{
  "name": "Acme Corporation",
  "address": "123 Main Street, City, State, ZIP",
  "email": "contact@acme.com"
}
```

**Request Fields:**
- `name` (string, required): Name of the organization
- `address` (string, required): Address of the organization
- `email` (string, required): Contact email of the organization

**Response (201 Created):**
```json
{
  "message": "Organization created successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Acme Corporation",
    "address": "123 Main Street, City, State, ZIP",
    "email": "contact@acme.com",
    "created_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: User already belongs to an organization
- `400 Bad Request`: Validation errors (missing required fields, invalid email format)
- `401 Unauthorized`: Invalid or missing authentication token

**Notes:**
- The authenticated user must not already belong to an organization
- After creating the organization, the user is automatically assigned the "admin" role
- The user is automatically associated with the created organization

---

### 2. Add HR User

Add a new HR user to the organization. Only organization admins can add HR users.

**Endpoint:** `POST /api/organizations/add-hr/`

**Authentication:** Required (Admin only)

**Request Body:**
```json
{
  "email": "hr@acme.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "password": "securepassword123"
}
```

**Request Fields:**
- `email` (string, required): Email address of the HR user (must be unique)
- `first_name` (string, required): First name of the HR user
- `last_name` (string, required): Last name of the HR user
- `password` (string, optional): Password for the HR user (minimum 8 characters). If not provided, a random password will be generated.

**Response (201 Created):**
```json
{
  "message": "HR user added successfully",
  "status": "success",
  "data": {
    "id": 2,
    "uuid": "123e4567-e89b-12d3-a456-426614174001",
    "email": "hr@acme.com",
    "role": {
      "id": 2,
      "uuid": "123e4567-e89b-12d3-a456-426614174002",
      "name": "hr"
    },
    "role_uuid": "123e4567-e89b-12d3-a456-426614174002",
    "is_active": true,
    "created_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: User must belong to an organization
- `403 Forbidden`: Only organization admin can add HR users
- `400 Bad Request`: Validation errors (email already exists, password too short, missing required fields)
- `401 Unauthorized`: Invalid or missing authentication token

**Notes:**
- Only users with the "admin" role can add HR users
- The HR user is automatically associated with the admin's organization
- If password is not provided, a random password will be generated
- The HR role must exist in the system (created via `create_roles` management command)

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

To obtain an access token, use the login endpoint at `/api/auth/login/`.

---

## Role-Based Access Control

### Create Organization
- **Required Role:** Any authenticated user (who doesn't already belong to an organization)
- **Organization Association:** User becomes admin of the created organization

### Add HR User
- **Required Role:** Admin
- **Organization Association:** HR user is added to the admin's organization

---

## Notes

- All timestamps are in ISO 8601 format (UTC)
- Email addresses must be unique across the system
- Password must be at least 8 characters long if provided manually
- Organization creation automatically assigns the "admin" role to the creator
- HR users can be added only by organization admins
- The HR role must exist in the system before adding HR users

---

## Example Workflow

1. **User Registration:** Register a new user at `/api/auth/register/`
2. **Login:** Login to get JWT tokens at `/api/auth/login/`
3. **Create Organization:** Create an organization at `/api/organizations/create/` (user becomes admin)
4. **Add HR User:** Add HR users to the organization at `/api/organizations/add-hr/`

---

## Error Codes Summary

| Status Code | Description |
|------------|-------------|
| 200 OK | Request successful |
| 201 Created | Resource created successfully |
| 400 Bad Request | Invalid request data or business rule violation |
| 401 Unauthorized | Missing or invalid authentication token |
| 403 Forbidden | Insufficient permissions |
| 500 Internal Server Error | Server error |

