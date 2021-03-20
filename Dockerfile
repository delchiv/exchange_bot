FROM python:3.8

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /src

COPY Pipfile Pipfile.lock /src/
RUN pip install pipenv && pipenv install --system

COPY . /src/