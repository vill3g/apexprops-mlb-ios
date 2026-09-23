from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime
import ipaddress

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u'US'),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u'Local'),
    x509.NameAttribute(NameOID.LOCALITY_NAME, u'Localhost'),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'Kalshi AI'),
    x509.NameAttribute(NameOID.COMMON_NAME, u'192.168.1.194'),
])

cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.datetime.now(datetime.UTC)
).not_valid_after(
    datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=3650)
).add_extension(
    x509.SubjectAlternativeName([
        x509.IPAddress(ipaddress.IPv4Address(u'192.168.1.194')), 
        x509.IPAddress(ipaddress.IPv4Address(u'127.0.0.1'))
    ]),
    critical=False,
).sign(key, hashes.SHA256())

with open('key.pem', 'wb') as f:
    f.write(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))

with open('cert.pem', 'wb') as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

print('Self-signed certificate generated: cert.pem and key.pem')
