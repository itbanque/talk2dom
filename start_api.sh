#!/bin/bash
export $(grep -v '^#' .env | xargs)
uvicorn talk2dom.api.main:app --host 0.0.0.0 --port 8000 --reload