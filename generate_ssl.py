"""
Generate a self-signed SSL certificate for local HTTPS development.

Usage:
    python generate_ssl.py

This creates ssl/cert.pem and ssl/key.pem in the project directory.
The certificate is valid for 1 year and is issued to 'localhost'.
"""

import os
import sys

try:
    from OpenSSL import crypto
except ImportError:
    print("Error: pyOpenSSL is not installed. Run: pip install pyOpenSSL")
    sys.exit(1)


def generate_ssl_certificate(output_dir="ssl", validity_days=365):
    """Generate a self-signed SSL certificate for localhost."""
    os.makedirs(output_dir, exist_ok=True)

    # Generate RSA key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # Create self-signed certificate
    cert = crypto.X509()
    subject = cert.get_subject()
    subject.C = "IN"
    subject.ST = "Development"
    subject.L = "Localhost"
    subject.O = "Care4U Hospital"
    subject.OU = "Development"
    subject.CN = "localhost"

    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(validity_days * 24 * 60 * 60)
    cert.set_issuer(subject)
    cert.set_pubkey(key)
    cert.sign(key, "sha256")

    cert_path = os.path.join(output_dir, "cert.pem")
    key_path = os.path.join(output_dir, "key.pem")

    with open(cert_path, "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    with open(key_path, "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

    print(f"✅ SSL certificate generated successfully!")
    print(f"   Certificate: {cert_path}")
    print(f"   Private Key: {key_path}")
    print(f"   Valid for:   {validity_days} days")
    print(f"\n   Run the app with: python app.py")
    print(f"   Then open: https://localhost:5000")
    print(f"\n   ⚠️  Your browser will show a security warning because this is")
    print(f"      a self-signed certificate. Click 'Advanced' → 'Proceed' to continue.")


if __name__ == "__main__":
    generate_ssl_certificate()
