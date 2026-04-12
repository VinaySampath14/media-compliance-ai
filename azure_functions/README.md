# Azure Functions — Deployment (Planned)

This folder will contain the Azure Functions deployment of the Media Compliance AI pipeline.

## Planned: HTTP Trigger

The `POST /audit` FastAPI endpoint will be packaged as an Azure Function HTTP trigger, allowing the pipeline to run fully serverless on Azure without a persistent server.

## Why Azure Functions

- Serverless — no server to manage or pay for when idle
- Scales automatically with request volume
- Integrates natively with Azure Video Indexer, AI Search, and OpenAI

## Status

> Not yet implemented. The pipeline currently runs via FastAPI (`backend/src/api/server.py`).
