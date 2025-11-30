# Candidate API Documentation

## Overview

The Candidate API provides endpoints for registering candidates and retrieving candidate information. Candidates are associated with organizations and can be managed by Admin and HR users.

**Base URL:** `/api/auth/`

**Authentication:** Most endpoints require JWT authentication. Include the access token in the Authorization header: `Authorization: Bearer <access_token>`

---

## Endpoints

### 1. Register Candidate

Register a new candidate in the system. Only Admin or HR users can register candidates.

**Endpoint:** `POST /api/auth/register/candidate/`

**Authentication:** Required (Admin or HR only)

**Request Body:**
```json
{
  "email": "candidate@example.com",
  "first_name": "John",
  "last_name": "Smith",
  "password": "optionalpassword123"
}
```

**Request Fields:**
- `email` (string, required): Email address of the candidate (must be unique)
- `first_name` (string, required): First name of the candidate
- `last_name` (string, required): Last name of the candidate
- `password` (string, optional): Password for the candidate. If not provided, a random 8-character password will be generated.

**Response (201 Created):**
```json
{
  "message": "Candidate registered successfully",
  "status": "success",
  "data": {
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174002",
    "email": "candidate@example.com",
    "first_name": "John",
    "last_name": "Smith",
    "created_at": "2024-12-01T10:00:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: User must belong to an organization to register candidates
- `403 Forbidden`: Only admin or HR can register candidates
- `400 Bad Request`: Validation errors (email already exists, missing required fields)
- `401 Unauthorized`: Invalid or missing authentication token

**Notes:**
- The candidate is automatically associated with the registering user's organization
- If password is not provided, a random 8-character password will be generated
- The password is encrypted and stored securely in the database
- The generated password can be retrieved later using the Get Candidates endpoint

---

### 2. Get Candidates

Retrieve all candidates belonging to the authenticated user's organization.

**Endpoint:** `GET /api/auth/candidates/`

**Authentication:** Required

**Query Parameters:** None

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
      "first_name": "John",
      "last_name": "Smith",
      "organization": "Acme Corporation",
      "password": "LafFNtpt",
      "created_at": "2024-12-01T10:00:00Z"
    },
    {
      "id": 2,
      "uuid": "123e4567-e89b-12d3-a456-426614174003",
      "email": "candidate2@example.com",
      "first_name": "Jane",
      "last_name": "Doe",
      "organization": "Acme Corporation",
      "password": "XyZ9aBc2",
      "created_at": "2024-12-01T11:00:00Z"
    }
  ]
}
```

**Response Fields:**
- `id` (integer): Unique identifier for the candidate
- `uuid` (string): UUID identifier for the candidate
- `email` (string): Email address of the candidate
- `first_name` (string): First name of the candidate
- `last_name` (string): Last name of the candidate
- `organization` (string): Name of the organization the candidate belongs to
- `password` (string): Plaintext password of the candidate (decrypted from stored encrypted password)
- `created_at` (string): ISO 8601 timestamp of when the candidate was created

**Error Responses:**
- `400 Bad Request`: User must belong to an organization to fetch candidates
- `401 Unauthorized`: Invalid or missing authentication token
- `500 Internal Server Error`: Server error

**Notes:**
- Only candidates belonging to the authenticated user's organization are returned
- The password field contains the decrypted plaintext password
- For candidates with old hashed passwords (before encryption was implemented), the password field may be `null`

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

To obtain an access token, use the login endpoint at `/api/auth/login/`.

---

## Role-Based Access Control

### Register Candidate
- **Required Role:** Admin or HR
- **Organization Association:** Candidate is automatically associated with the registering user's organization

### Get Candidates
- **Required Role:** Any authenticated user
- **Organization Filter:** Only candidates from the user's organization are returned

---

## Password Management

### Password Storage
- Passwords are encrypted using Fernet (AES-128) encryption before storage
- Each password is encrypted with a unique salt
- The encryption key is derived using PBKDF2 key derivation function

### Password Retrieval
- Passwords can be retrieved in plaintext using the Get Candidates endpoint
- The system supports both encrypted (new) and hashed (old) passwords
- For old hashed passwords, the password field will be `null` in the response

### Password Generation
- If no password is provided during registration, a random 8-character password is generated
- Generated passwords contain letters (both uppercase and lowercase) and digits
- The generated password is automatically encrypted and stored

---

## Notes

- All timestamps are in ISO 8601 format (UTC)
- Email addresses must be unique across the system
- Candidates are automatically associated with the registering user's organization
- Only Admin and HR users can register new candidates
- All authenticated users can view candidates from their organization
- Passwords are encrypted, not hashed, allowing retrieval of plaintext passwords
- The organization name is returned as a string in the response, not as an object

---

## Example Workflow

1. **Login:** Login as Admin or HR user at `/api/auth/login/`
2. **Register Candidate:** Register a new candidate at `/api/auth/register/candidate/`
   - Optionally provide a password, or let the system generate one
3. **Get Candidates:** Retrieve all candidates at `/api/auth/candidates/`
   - View candidate details including decrypted passwords

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

---

## Security Considerations

1. **Password Encryption:** Passwords are encrypted using industry-standard encryption (Fernet/AES-128)
2. **Salt Usage:** Each password uses a unique salt for encryption
3. **Key Derivation:** Encryption keys are derived using PBKDF2 with 100,000 iterations
4. **Access Control:** Only authorized users (Admin/HR) can register candidates
5. **Organization Isolation:** Users can only view candidates from their own organization

---

## Migration Notes

- Candidates created before the encryption implementation may have hashed passwords
- For these candidates, the password field in the Get Candidates response will be `null`
- To update old candidates to use encrypted passwords, reset their passwords through the registration process or update mechanism

