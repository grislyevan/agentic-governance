# Agent installers baked into the Docker API image

Files in this directory are **copied into the image** at `docker compose build` (see `Dockerfile.api`). After you rebuild the **api** service, dashboard agent downloads use these installers without any host mount.

## Workflow

1. Copy **`detec-agent.zip`**, **`DetecAgentSetup.exe`**, and/or **`detec-agent-linux.tar.gz`** here (filenames the API expects; see [SERVER.md](../../SERVER.md) Agent downloads).
2. Run **`docker compose build api`** (or full stack build), then **`docker compose up -d`**.

Pushing to git does not change what is inside the image until you rebuild after placing installers here (or your CI copies artifacts in before `docker build`).

## Optional host override

To test new installers without rebuilding the image, uncomment the `./dist/packages` volume in `docker-compose.yml` (dev only). That mount replaces `/data/packages` in the container.
