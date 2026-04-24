import multiprocessing
import os

bind = "127.0.0.1:8000"
workers = (2 * multiprocessing.cpu_count()) + 1
worker_class = "sync"
timeout = 90
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
max_requests = 1000
max_requests_jitter = 100

# --- HTTPS / SSL Configuration ---
# When running Gunicorn directly with SSL (without Nginx reverse proxy),
# set GUNICORN_SSL=1 and ensure ssl/cert.pem & ssl/key.pem exist.
#
# Recommended: Use Nginx or ALB for SSL termination instead. In that case,
# leave GUNICORN_SSL=0 (default) and Gunicorn serves plain HTTP to Nginx.

if os.getenv("GUNICORN_SSL", "0") == "1":
    ssl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ssl")
    certfile = os.path.join(ssl_dir, "cert.pem")
    keyfile = os.path.join(ssl_dir, "key.pem")

    if os.path.exists(certfile) and os.path.exists(keyfile):
        certfile = certfile
        keyfile = keyfile
        bind = "0.0.0.0:443"
    else:
        print(f"WARNING: GUNICORN_SSL=1 but cert files not found in {ssl_dir}")

# Forward proxy headers (essential when behind ALB/Nginx)
forwarded_allow_ips = "*"
secure_scheme_headers = {
    "X-Forwarded-Proto": "https",
}
