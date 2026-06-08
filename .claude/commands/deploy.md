Deploy the current codebase to Railway and confirm the deployment is live.

## Step 1 — Verify branch and working tree
Run:
```bash
git branch --show-current
git status --short
```

- If not on `main`, stop and say:
  "Switch to main before deploying. You are currently on <branch>."
- If there are uncommitted changes, stop and say:
  "Uncommitted changes detected. Commit or stash them before deploying."

## Step 2 — Deploy to Railway
Run:
```bash
RAILWAY_CALLER=skill:use-railway@1.2.4 railway up --detach -m "deploy: $(git log -1 --pretty=%s)"
```

Report: "✓ Build queued — deploying latest main to Railway"

## Step 3 — Poll until deployment completes
Poll `railway deployment list --json` every 10 seconds until the newest
deployment's `status` is `SUCCESS`, `FAILED`, or `CRASHED`:

```bash
until railway deployment list --json 2>/dev/null | python3 -c \
  "import json,sys; d=json.load(sys.stdin); s=d[0]['status'] if d else 'none'; print(s); exit(0 if s in ['SUCCESS','FAILED','CRASHED'] else 1)"; \
  do sleep 10; done
```

## Step 4 — Report outcome

If `SUCCESS`:
```
✓ Deployed successfully
🌐 https://expense-tracker-production-1fd0.up.railway.app
```

If `FAILED` or `CRASHED`:
- Run `railway logs --lines 50` to fetch the tail of the build/runtime logs
- Print the relevant error lines
- Say: "Deployment failed — see logs above"

## Rules
- Never deploy from a branch other than `main`
- Never deploy if there are uncommitted local changes
- Always wait for a terminal status — never report success on a queued build
- If `railway` CLI is not found, say: "Railway CLI not installed. Run: bash <(curl -fsSL https://railway.com/install.sh)"
