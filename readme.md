[![CI](https://github.com/docfrench/deimos_api/actions/workflows/ci.yml/badge.svg)](https://github.com/docfrench/deimos_api/actions/workflows/ci.yml)

This is a repo of the API supporting my personal homelab website.

Features:
- Aggregates stats for media libraries: Jellyfin, BookOrbit.
- Leverages an SQLite database to dynamically present playable Interactive Fiction games.
- Leverages an SQLite database to provide a login-less game where the player attempts to discern AI-written fiction from human-written fiction.
- Leverages an SQLite database for hosting a tabletop RPG campaign website.

Tech stack for the API
- FastAPI
- Docker for containerization
- Deployment through Github Actions CI/CD
- Currently leverages a locally hosted Github runner to automatically deploy.

The website
- nginx container for the website
- nginx Proxy Manager as reverse proxy for routing external requests

Setup / User
- Create .env by using .env.example as a template
- docker pull ghcr.io/docfrench/deimos-api:latest
- or use the following docker-compose yaml

```
services:
  api:
    image: ghcr.io/docfrench/deimos-api:latest
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
```

Setup / Development

- git clone repo locally
- edit .env.example with your details and change to .env
- create a venv and pip install -r requirements.txt


