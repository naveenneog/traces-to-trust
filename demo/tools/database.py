"""Mock database tool — simulates customer lookup with realistic delay."""
import time
import random

MOCK_CUSTOMERS = {
    "C-1001": {"name": "Acme Corp", "tier": "Enterprise", "region": "APAC", "arr": 450000},
    "C-1002": {"name": "TechFlow Inc", "tier": "Premium", "region": "EMEA", "arr": 120000},
    "C-1003": {"name": "DataBridge Ltd", "tier": "Standard", "region": "Americas", "arr": 45000},
}

def lookup_customer(customer_id: str) -> dict:
    time.sleep(random.uniform(0.05, 0.15))  # simulate DB query
    if customer_id in MOCK_CUSTOMERS:
        return {"status": "found", "customer": MOCK_CUSTOMERS[customer_id]}
    return {"status": "not_found", "customer_id": customer_id}

def get_purchase_history(customer_id: str, limit: int = 5) -> dict:
    time.sleep(random.uniform(0.1, 0.2))
    products = ["Azure OpenAI", "Copilot Studio", "Fabric", "Foundry Agent Service", "Defender"]
    history = [
        {"product": random.choice(products), "date": f"2026-0{random.randint(1,4)}-{random.randint(1,28):02d}",
         "amount": random.randint(1000, 50000)}
        for _ in range(min(limit, random.randint(2, 5)))
    ]
    return {"customer_id": customer_id, "purchases": history}

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "lookup_customer",
        "description": "Look up customer information by customer ID",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID, e.g. 'C-1001'"},
            },
            "required": ["customer_id"],
        },
    },
}
