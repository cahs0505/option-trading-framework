from optiontrader.logging_config import setup_logging

bind = "0.0.0.0:8000"
workers = 4
accesslog = "-"      # still needed so Gunicorn generates access log records
errorlog = "-"
loglevel = "info"

def post_fork(server, worker):
    setup_logging(log_level="INFO")