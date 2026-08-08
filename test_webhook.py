import asyncio
from fastapi.testclient import TestClient
from app import app
import json

client = TestClient(app)

payload = {
    "event_id": "evt_123",
    "event_type": "transaction.completed",
    "data": {
        "id": "txn_123",
        "custom_data": {
            "email": "test@example.com"
        },
        "details": {
            "line_items": [
                {
                    "price": {
                        "id": "pri_01kzh3b2kr5yynf085b689wjpp"
                    }
                }
            ]
        }
    }
}

response = client.post("/api/billing/paddle/webhook", json=payload)
print(response.status_code)
print(response.json())
