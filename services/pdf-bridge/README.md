# PDF Bridge

This service exposes the two HTTP endpoints referenced by Demo4:

- `POST /inspect` — inspect PDF pages and classify native text/OCR pages.
- `POST /extract` — extract selectable PDF text for selected pages.

The same image is built twice by `deployment/docker-compose.pdf-services.yaml` so the workflow can keep its original container names:

- `dify-pdf-bridge-inspect-test-v2`
- `dify-pdf-bridge-extract-test`

The service uses Python 3.12, Flask 3.1.2, Requests 2.32.5, and PyMuPDF 1.24.14.

