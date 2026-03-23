# MDM deployment (macOS)

Detec no longer ships a packaged macOS endpoint agent in this repository. Endpoint coverage is **Windows** and **Linux** via the dashboard **Deploy Agent** flow.

The collector (scanner architecture) still runs on macOS when installed from source for development (`pip install -e .` and `python -m collector.main` or `detec-agent`). There is no supported `.pkg` or MDM installer path here.

For Windows fleet deployment, see [DEPLOY.md](../DEPLOY.md).
