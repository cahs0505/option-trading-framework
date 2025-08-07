FROM python:3.11.13-slim-bookworm

# set a directory for the app
WORKDIR /app

COPY requirements.txt .
COPY setup.py .
COPY script.py .
COPY optiontrader ./optiontrader

RUN apt-get update && \
    apt-get -y install libpq-dev gcc 
 
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

RUN pip install .

# tell the port number the container should expose
EXPOSE 5000

# run the command
CMD ["python", "-u", "script.py", "-r", "-p"]

