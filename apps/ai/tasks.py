from BilimAI.celery import app


@app.task
def ping_celery():
    return "pong"
