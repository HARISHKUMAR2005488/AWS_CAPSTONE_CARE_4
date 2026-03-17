import multiprocessing

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
