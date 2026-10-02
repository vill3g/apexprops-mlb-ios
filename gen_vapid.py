import os
import json
from pywebpush import webpush, WebPushException

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    import base64

    # Generate EC private key
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    
    # Get private value
    priv_val = private_key.private_numbers().private_value.to_bytes(32, 'big')
    
    # Get public key numbers
    pub = private_key.public_key().public_numbers()
    pub_val = b'\x04' + pub.x.to_bytes(32, 'big') + pub.y.to_bytes(32, 'big')
    
    def encode_b64url(data):
        return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

    vapid_private_key = encode_b64url(priv_val)
    vapid_public_key = encode_b64url(pub_val)

    keys = {
        "private_key": vapid_private_key,
        "public_key": vapid_public_key
    }
    
    os.makedirs("backend/data", exist_ok=True)
    with open("backend/data/vapid.json", "w") as f:
        json.dump(keys, f)
    
    print("VAPID keys generated successfully!")
except Exception as e:
    print(f"Error: {e}")
