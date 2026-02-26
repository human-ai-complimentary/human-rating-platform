# Render Production Config

This repo does not store production runtime secrets.

## Source of truth

1. **Render Blueprint (`render.yaml`)**
- Defines services, build/start commands, and `autoDeployTrigger: checksPass`.

2. **Render Secret Group**
- Stores runtime secrets (`DATABASE__URL`, auth/provider keys, API keys).
- Attach the same group to API and web services as needed.

3. **GitHub branch protection + CI**
- `.github/workflows/main.yml` must pass before merge.
- Owner/admin approval happens at PR merge policy, not via custom deploy hooks.

## First-time setup

1. Create services from `render.yaml` (Blueprint sync).
2. In Render, create and attach a Secret Group to services.
3. Set API/web public env vars in Render:
- API: `APP__CORS_ORIGINS`
- Web: `VITE_API_HOST`, `VITE_API_PREFIX`
4. In Render service settings, confirm auto-deploy is enabled and tied to checks passing.

## Manual operations

- Manual deploy/redeploy: use Render dashboard (`Manual Deploy`).
- Rollback: use Render dashboard deploy history.
- Logs: use Render service logs/events.
