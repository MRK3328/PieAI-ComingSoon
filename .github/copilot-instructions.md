<!--
Brief AI agent instructions for the "Pie AI | Coming Soon" Flask project.
Keep this file concise (20-50 lines). It should provide actionable, repo-specific hints
so an automated coding assistant can be immediately productive.
-->

# Copilot instructions — Pie AI (ComingSoon)

Purpose
- Small Flask app that serves a single landing page. The app root is `app.py`. Templates live in `templates/` and static assets in `Static/` (note capital S).

Quick tasks an AI can do
- Add routes in `app.py` (Flask): follow the existing `@app.route('/')` pattern and use `render_template()` to render files from `templates/`.
- Add or modify templates under `templates/`; use `url_for('static', filename='IMAGES/...')` to reference assets (see `index.html`).
- Add static files under `Static/` (CSS, JS, IMAGES). Note the non-standard capitalized `Static` directory.

How to run locally (developer workflow)
- Run the Flask app directly with Python: `python app.py`. The app uses `app.run(debug=True)` in `app.py` so it runs in debug mode by default.

Project conventions & gotchas
- Directory names: static files are served from `Static/` (capital S). When referencing with Flask's `url_for`, the template uses `static` as the endpoint but the physical folder is `Static/` in this repo — keep paths consistent with how `app.py` and Flask are configured.
- Minimal structure: there are no package files (requirements.txt, venv) in the repo. If adding dependencies, update `requirements.txt` at repo root.
- No build/test harness: tests and CI are not present. Propose tests using pytest and a minimal `requirements.txt` when adding server-side logic.

Examples from the codebase
- Route example (in `app.py`):
  @app.route('/')
  def home():
      return render_template('index.html')

- Template example (in `templates/index.html`): use `{{ url_for('static', filename='IMAGES/PCbackgorund.png') }}` to load images from the static folder.

When editing
- Keep edits minimal and focused. Preserve the simple, single-responsibility design: `app.py` is the web server, templates are static HTML/CSS.
- If adding features that change runtime dependencies, add a `requirements.txt` and update this file with the new run commands.

Files to inspect first
- `app.py` — entrypoint and routing
- `templates/index.html` — main UI and static asset usage
- `Static/` — CSS, JS, IMAGES used by templates

Follow-up
- If you (human) want CI, API endpoints, or a front-end build, say which feature to add. I'll propose a minimal implementation (requirements, tests, and run/CI steps).
