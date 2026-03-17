# CARE_4_U Modular API

## Folder Structure

- `care4u_api/auth` - JWT authentication endpoints
- `care4u_api/appointments` - booking APIs
- `care4u_api/notifications` - SNS APIs
- `care4u_api/chatbot` - NLP chatbot APIs
- `care4u_api/services` - DynamoDB/SNS/chatbot service layer
- `care4u_api/middleware` - JWT route protection
- `care4u_api/utils` - response, validation, logging, security helpers

## DynamoDB Design

- Users table: `user_id` (PK)
- Appointments table: `appointment_id` (PK)
- Appointments GSI: `user_id-index` with partition key `user_id`

## Run

```bash
pip install -r requirements.txt
gunicorn api_server:app
```

## Main API Prefix

- `/api/v1/auth`
- `/api/v1/appointments`
- `/api/v1/notifications`
- `/api/v1/chatbot`
