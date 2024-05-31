FROM python:3.11-bullseye

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

ADD coordimate-decc2-16cded94d287.json .
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/coordimate-decc2-16cded94d287.json"

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "routes:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
