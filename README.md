# HAPPY Project Suite

This repository contains the four HAPPY applications as separate top-level projects:

- `HAPPY_PLATFORM_CODEX/` - HAPPY Management Platform, API, worker, and internal web application
- `CV-Parser-main/` - CV parsing service and its dedicated frontend
- `frontend/` - participant data-collection frontend
- `portal/` - Employer Acquisition Portal

The authoritative HAPPY Platform setup, architecture, roadmap, and verification
instructions are in [`HAPPY_PLATFORM_CODEX/README.md`](HAPPY_PLATFORM_CODEX/README.md).

## HAPPY Platform verification

Run platform commands from its project directory:

```bash
cd HAPPY_PLATFORM_CODEX
pnpm install --frozen-lockfile
pnpm verify
```

GitHub Actions runs the same verification from `HAPPY_PLATFORM_CODEX/`. The Render
Blueprint is located at `HAPPY_PLATFORM_CODEX/render.yaml` and uses the nested
platform directory as its Docker build context.
