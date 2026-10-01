<div align="left">

![GitHub Actions](https://img.shields.io/badge/github%20actions-%232671E5.svg?style=for-the-badge&logo=githubactions&logoColor=white)
![Python](https://img.shields.io/badge/python-%233670A0.svg?style=for-the-badge&logo=python&logoColor=ffdd54)
[![CI](https://github.com/docfrench/deimos_api/actions/workflows/ci.yml/badge.svg)](https://github.com/docfrench/deimos_api/actions/workflows/ci.yml)

</div>

## Deimos API
This is a repo of the API that supports my personal homelab website.

### Features:
- The API aggregates and presents statistics for media libraries: Jellyfin, BookOrbit.
- It leverages SQLite databases to perform the following:
  - Host the live data for a tabletop RPG campaign website 
  - Dynamically present playable Interactive Fiction games (the Zork kind)
  - Provide a zero-login web game, where the player attempts to discern AI-written fiction from human-written fiction.

### Tech stack for the API
- FastAPI provides the backend wiring
- SQLite as a light, serverless database solution to persist data
- Docker provides containerization
- Deployment through Github Actions CI/CD
  - A locally hosted Github runner on my server automatically deploys a new image on a successful main branch push

### Other related networking
- The website itself is hosted on an nginx container
- nginx Proxy Manager (NPM) provides a reverse proxy for internal routing to different Docker containers
- Resilience to dynamic DNS provided by: [cloudflare-ddns](https://github.com/timothymiller/cloudflare-ddns)

### Setup / User
(This framework is rather personalized to my specific needs, but feel free to try it out)
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

### Setup / Development

- git clone repo locally
- edit .env.example with your details and change to .env
- create a venv and pip install -r requirements.txt


