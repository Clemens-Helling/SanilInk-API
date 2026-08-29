#!/usr/bin/env python
"""Verify JWT token structure and content."""

import jwt
import json

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjozLCJ1c2VybmFtZSI6InRlc3QtdXNlciIsImVtYWlsIjoidGVzdC1mZjU3MWVAZXhhbXBsZS5jb20iLCJjdXN0b21lcl9pZCI6MywiaWF0IjoxNzg2NTMwODMwLCJleHAiOjE3ODY2MTcyMzB9.gyjFIWtrGmMhx78RL7CWgBBvbpcy5pCpT-tylTJJuTA"

decoded = jwt.decode(token, options={"verify_signature": False})

print("JWT Token Structure:")
print("=" * 60)
print(json.dumps(decoded, indent=2))
print("=" * 60)
