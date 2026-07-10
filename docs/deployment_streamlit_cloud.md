# Streamlit Cloud Deployment Guide

This guide describes the recommended cloud setup for using the MVP from a phone without keeping a local computer running.

## Target Architecture

```text
Phone browser
  -> Streamlit Community Cloud app
  -> Cloud MySQL database
  -> DeepSeek API
```

The app should not depend on `localhost` in production.

## Required Services

- GitHub repository with the latest code.
- Streamlit Community Cloud app connected to the repository.
- A cloud MySQL database from a provider such as Railway, Aiven, or a VPS-hosted MySQL instance.
- DeepSeek API key.

## Streamlit App Settings

Recommended Streamlit Cloud settings:

```text
Repository: dhzhang41-tech/ai-fitness-coach
Branch: main
Main file path: main.py
Python version: 3.11+
```

## Secrets

Do not commit `.env` to GitHub.

Set these values in Streamlit Cloud secrets:

```toml
DEEPSEEK_API_KEY = "your_deepseek_key_here"
MYSQL_HOST = "your_cloud_mysql_host"
MYSQL_PORT = 3306
MYSQL_USER = "your_cloud_mysql_user"
MYSQL_PASSWORD = "your_cloud_mysql_password"
MYSQL_DATABASE = "ai_fitness_coach"
```

Local development can still use `.env`.

## Database Notes

Many managed MySQL providers do not allow the app user to run `CREATE DATABASE`.

Recommended setup:

1. Create the database in the provider dashboard.
2. Put the database name into `MYSQL_DATABASE`.
3. Let the app create or patch tables on startup with `init_db()`.

## Deployment Checklist

- GitHub `main` branch is up to date.
- `.env` is not tracked by git.
- `requirements.txt` contains Streamlit, MySQL connector, LangGraph, ChromaDB, and OpenAI client.
- Streamlit secrets are configured.
- Cloud MySQL allows inbound connections from Streamlit Cloud.
- Database name in secrets already exists.
- App starts without local-only paths.

## MVP Usage

After deployment, open the Streamlit app URL from your phone browser.

For the MVP phase, use the app mainly to:

- enter daily readiness;
- run workouts;
- use conservative mid-workout replanning;
- log completion;
- review the data after 2-4 weeks.

