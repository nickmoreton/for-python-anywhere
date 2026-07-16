# Wagtail Platform Dashboard Design

## Summary

Add a read-only **Platform** dashboard to the Wagtail admin. The dashboard will be linked from the admin sidebar, visible and accessible only to superusers, and will show a page-load snapshot of safe application and infrastructure information.

The feature will live in a dedicated `app.platform_dashboard` Django app so operational concerns remain separate from public site content.

## Goals

- Add a **Platform** item to the Wagtail admin sidebar for superusers.
- Serve the dashboard at `/admin/platform/` using Wagtail admin styling.
- Show safe application, deployment, and infrastructure information.
- Collect fresh values once per page request; no background polling or automatic refresh is required.
- Degrade individual unavailable readings without preventing the dashboard from rendering.
- Prevent non-superusers from viewing either the menu item or the dashboard.

## Non-goals

- Editing settings or infrastructure from the dashboard.
- Monitoring history, alerts, charts, or background collection.
- Showing secrets, credentials, complete environment-variable contents, or database connection details.
- Replacing a production monitoring or observability service.
- Reporting PythonAnywhere account quotas when the operating system only exposes filesystem or host-level values.

## Architecture

Create `app.platform_dashboard` and add it to `INSTALLED_APPS`. The app will contain four responsibilities:

1. `wagtail_hooks.py` registers the admin URL and sidebar menu item.
2. A view enforces superuser access, requests a platform snapshot, and renders the template.
3. A collector module gathers and formats platform values independently of HTTP and templates.
4. A Wagtail admin template renders the returned sections and fields.

The sidebar item and URL registration will use Wagtail's supported admin hooks. A standalone hook-based view is preferred over a Wagtail `ViewSet` because the feature has one read-only page and no CRUD workflow.

Add `psutil` as a locked project dependency for portable CPU, memory, disk, and process readings. Standard Python, Django, and Wagtail APIs will provide the remaining values. Production deployment publishes its validated commit to an ignored `.deployed-commit` file immediately before reloading WSGI. The collector reads that file first and uses a bounded, non-interactive Git command only as a local-development fallback.

## Access Control

The menu item's visibility check will return true only for an authenticated superuser. Hiding the menu is not the security boundary: the view will independently enforce the same policy.

- Anonymous requests are redirected to the Wagtail admin login.
- Authenticated Wagtail admin users who are not superusers receive HTTP 403.
- Authenticated users without Wagtail admin access follow Wagtail's standard admin-login redirect, because Wagtail rejects them before the registered view runs.
- Superusers receive the dashboard.

No platform detail is placed in the URL, redirect, or error response for an unauthorized request.

## Dashboard Content

The dashboard uses Wagtail's standard admin base template, header, spacing, and responsive layout. It has a **Platform** heading and a timezone-aware timestamp identifying when the snapshot was collected.

### Application section

- Environment: `Development` when Django `DEBUG` is enabled, otherwise `Production`.
- Python version.
- Django version.
- Wagtail version.
- Database engine vendor only, such as `MySQL`; host, port, database name, username, password, and options are excluded.
- Debug status, displayed clearly as enabled or disabled.
- Machine hostname.
- Current Git commit as a short SHA.

### Infrastructure section

- Operating system name and release.
- Machine architecture.
- Physical and logical CPU counts.
- CPU load averages over the last 1, 5, and 15 minutes.
- Total, used, and available memory, plus utilization percentage.
- Total, used, and free space, plus utilization percentage, for the filesystem containing Django's `BASE_DIR`.
- Current Django process uptime.

Labels must state that disk values describe the project filesystem, not a hosting account quota. Uptime must be labelled as process uptime, not machine or site uptime.

The page is read-only. Values refresh only when the browser requests the page again.

## Data Model and Flow

No database model or migration is required.

For each request:

1. The access check authenticates and authorizes the requester.
2. The view calls the collector once.
3. The collector creates a single timestamped snapshot.
4. Each metric is gathered independently and converted into a display field containing a label and formatted value, with optional status metadata for presentation.
5. The collector returns application and infrastructure sections to the view.
6. The template renders the supplied records without performing system calls, Git commands, calculations, or secret filtering.

Human-readable byte values, durations, and load averages will use consistent deterministic formatting so they are easy to test. Collection must not add a noticeable delay to normal admin use.

## Failure Handling and Logging

Each metric boundary catches expected availability errors independently. Examples include restricted host metrics, an unsupported platform API, missing deployment revision and Git metadata, a missing Git executable, or a process ending during inspection. The affected field displays `Unavailable`, while all other fields continue to render.

Unexpected collection errors are logged server-side with enough context to identify the failed metric, but raw exception details are not rendered in the page. Secret values must not be included in log context.

The deployment revision file must contain the validated full 40-character SHA and be published atomically before WSGI reload. The local Git fallback must have a short timeout and must not invoke a shell. Infrastructure reads must remain local and perform no network requests.

## Security and Privacy

The collector uses an allowlist of fields rather than enumerating settings or environment variables. It must never return or render:

- Django's secret key.
- Database names, usernames, passwords, hosts, ports, or connection options.
- Environment-variable names or values.
- API keys, tokens, cookies, session data, or request headers.
- Full configuration dumps.

The database value is derived only from Django's active connection vendor. Debug status is shown because access is restricted to superusers and is operationally relevant.

## Testing

Tests will cover the integration and the collector as separate units.

### Admin integration tests

- An anonymous request redirects to the Wagtail login.
- An authenticated Wagtail admin non-superuser receives HTTP 403 at the direct URL.
- An authenticated user without Wagtail admin access is redirected through Wagtail's admin-login flow.
- A superuser receives HTTP 200 and the Wagtail dashboard template.
- Both dashboard sections and representative values are rendered from a mocked snapshot.
- The Platform menu item is shown to superusers and hidden from non-superusers.
- Representative secret and database credential values are absent from the response.

### Collector tests

- Application versions, environment, database vendor, hostname, and Git SHA are mapped and formatted correctly.
- CPU load-average, memory, disk, and process uptime readings are mapped and formatted correctly from mocked `psutil` values.
- The collector prefers the deployment-published revision and falls back to a bounded Git lookup when it is absent or invalid.
- Bytes, percentages, and durations have deterministic output.
- Failure of each external boundary produces `Unavailable` for that field without removing successful fields.
- A complete snapshot retains successful sibling fields when one real metric boundary fails.
- The returned snapshot contains a timezone-aware collection timestamp.

Project-level verification will run the existing Django test suite, `manage.py check`, and `makemigrations --check --dry-run`. Since the feature adds no models, the migration check must remain clean.

## Repository Impact

Expected changes are limited to:

- A new `app/platform_dashboard/` application with hooks, view, collector, template, and tests.
- `app/settings/base.py` to install the app.
- `pyproject.toml` and `uv.lock` to add and lock `psutil`.
- `scripts/deploy.sh` to publish `.deployed-commit` atomically before reloading WSGI.
- `.gitignore`, `.dockerignore`, and deployment integration tests to keep the runtime revision out of source and container build contexts while verifying deployment order.

The public URL configuration, public templates, frontend Sass/JavaScript pipeline, deployment workflow, and database schema do not need to change.

Because this feature changes the documented project structure and dependency set, `AGENTS.md` should be reviewed during implementation and updated if its repository map or supported setup instructions would otherwise become inaccurate.
