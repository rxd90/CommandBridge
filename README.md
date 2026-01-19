# CommandBridge

CommandBridge is a demo internal developer portal built as a GitHub Pages static site. It showcases a cohesive GitHub-dark-minimal UI for incident management, status visibility, operational actions, and knowledge base runbooks.

## Run locally

Open the static site directly in your browser:

- `docs/index.html`

No build step or dependencies required.

## GitHub Pages

This repo is configured for GitHub Pages on the **main** branch, served from the `/docs` folder.

## Workflow demos

Operational workflows are simulated in GitHub Actions. To run them:

1. Go to the **Actions** tab.
2. Choose a workflow (e.g., Enable Maintenance Mode, Clear Cache, Failover Region).
3. Click **Run workflow** and fill in the inputs.

## Safety note

All workflows are **simulated** and only print structured logs. They do not modify infrastructure or require secrets.
