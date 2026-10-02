import time
from collections import defaultdict

rate_limit_records = defaultdict(list)
client_ip = "127.0.0.1"

# Simulate 300 requests over 1 minute
for i in range(300):
    now = time.time()
    rate_limit_records[client_ip] = [t for t in rate_limit_records[client_ip] if now - t < 60.0]
    if len(rate_limit_records[client_ip]) > 200: # Old limit
        print(f"Hit old limit at request {i}")
    if len(rate_limit_records[client_ip]) > 5000:
        print(f"Hit new limit at request {i}")
    rate_limit_records[client_ip].append(now)
    # Don't sleep, simulate them coming in instantly

print(f"Total records kept: {len(rate_limit_records[client_ip])}")
