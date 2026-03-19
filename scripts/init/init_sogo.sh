#!/bin/bash

cd /workspace/scripts/init

# curl -X PATCH -H 'Content-Type: application/json' -d @system_settings.json http://localhost:5000/api/admin/v1/config/system
# curl -X PATCH -H 'Content-Type: application/json' -d @domain_settings.json http://localhost:5000/api/admin/v1/config/domain-default

# Login and retrieve JWT token
LOGIN_RESPONSE=$(curl -s -X POST \
  'http://localhost:5000/api/user/v1/auth/login' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "username": "sogo-tests1@example.org",
  "password": "sogo"
}')

JWT_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"jwt_token"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)

if [ -z "$JWT_TOKEN" ]; then
  echo "Error: failed to retrieve JWT token. Login response:"
  echo "$LOGIN_RESPONSE"
  exit 1
fi

# Create external account
curl -X POST \
  'http://localhost:5000/api/user/v1/mailboxes' \
  -H 'accept: application/json' \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "Thibault KERIVEN",
  "mail_server": {
    "server": "192.168.69.31",
    "port": 10143,
    "encryption": "SSL/TLS",
    "type": "imap",
    "password": "Banane2!",
    "username": "tkeriven@snapshot.alinto.org",
    "auth_mech": "plain"
  },
  "receipts": {},
  "identities": [
    {
      "mail": "user@example.com",
      "name": "John Doe",
      "replyTo": "noreply@example.com",
      "isDefault": true,
      "signatures": {
        "default": "Best regards,\nJohn Doe",
        "professional": "Sincerely,\nJohn Doe"
      }
    }
  ],
  "certificates": {},
  "mail_outgoing": {
    "server": "smtp.example.com",
    "port": 587,
    "encryption": "SSL/TLS",
    "password": "secure_password",
    "username": "user@example.com",
    "auth_mech": "plain",
    "type": "smtp"
  }
}'
