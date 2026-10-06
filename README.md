# Gravik Opportunity Agent V4 Free

A source-aware opportunity radar for a B.Tech Chemical Engineering student. V4 is built from V3.1 and removes the paid OpenAI dependency.

## What V4 Free includes

- Research internships
- Industrial internships
- Professor/lab openings
- Fellowships
- Hackathons
- Technical competitions
- Paper/poster calls
- Open lab visits
- Industry/plant/R&D visits
- Workshops and bootcamps
- Courses and certificates
- Conferences, seminars and webinars
- IIT/IISc/CSIR/Central University discovery
- IIChE discovery
- Tamil Nadu/Chennai preference boost
- Public Unstop/Internshala/Naukri discovery when a permitted search API is configured
- Public company career pages and professor/lab pages through configured sources/search
- Deadline extraction and expired-opportunity filtering
- 7/3/1-day deadline alerts
- Duplicate detection and content/deadline change tracking
- Already-sent suppression
- Already-applied/ignored/saved tracking
- Preference learning from Telegram actions
- Deterministic eligibility checks
- Optional Gemini AI extraction/eligibility
- Telegram daily digest and action buttons
- robots.txt checking
- SQLite opportunity/source history
- GitHub Actions automation
- No OpenAI API, OpenAI package, or OpenAI secret

## Architecture

```text
Public pages / RSS / Sitemap / permitted search API
                    |
                    v
              Source collector
                    |
                    v
          robots + normalization
                    |
                    v
        Gemini (optional) --------+
                    |             |
                    +--> fallback |
                          parser  |
                    \             /
                     v           v
                Eligibility + dates
                         |
                         v
                 Fit + preferences
                         |
                         v
                      SQLite
                    /        \
                   v          v
             Daily digest  Deadline alerts
                   \          /
                    v        v
                      Telegram
```

## AI modes

### Mode A — $0 AI-service cost path

Leave `GEMINI_API_KEY` unset.

The deterministic parser still:
- extracts common deadline formats;
- filters expired opportunities;
- detects obvious year/CGPA disqualifiers;
- assigns eligibility status;
- scores Chemical Engineering/research/internship relevance;
- applies Tamil Nadu/Chennai boosts;
- preserves history and Telegram actions.

It is intentionally conservative and may mark more items as `unclear` or `likely_eligible`.

### Mode B — Optional Gemini free tier

Set:
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (default `gemini-3.8-flash`)

V4 uses Google's current `google-genai` SDK. If Gemini fails, the run automatically falls back to the deterministic parser.

Important: a free API tier is subject to Google's current quotas/availability. This project does not require a paid API subscription.

## Secrets

Required:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional:
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `BRAVE_SEARCH_API_KEY`

There are no `OPENAI_API_KEY` or `OPENAI_MODEL` settings.

### Discovery limitation

Unstop, Internshala and Naukri are not scraped through accounts, cookies, CAPTCHAs or access-control bypasses. Their V4 adapters use permitted public search discovery only when `BRAVE_SEARCH_API_KEY` is configured. Without it, those sources remain inactive.

LinkedIn private/personal feeds are not scraped. Public official pages can be configured where permitted.

## User profile

The included profile is:
- CIT, Coimbatore
- B.Tech Chemical Engineering
- 2nd year / 3rd semester
- approximate CGPA 8.70
- latest semester GPA 8.92
- interests in research, process engineering, catalysis, simulation, AI/ML, sustainability, energy, materials and data science

If the exact transcript CGPA differs, update `config.py`.

## Eligibility engine

The AI is not the only eligibility gate.

Examples:

`3rd/4th year only` + profile `2nd year`
→ `not_eligible`

`Engineering students` + Chemical Engineering profile
→ `likely_eligible` unless the source provides a stricter condition

Missing eligibility information
→ `unclear`

Nomination/professor approval/institution approval/conditional CGPA requirement
→ `conditional`

`not_eligible` items are stored for audit/history but excluded from the daily digest.

## Deadline alerts

Configured alerts:
- 7 days
- 3 days
- 1 day

Expired deadlines are filtered during ingestion and again during candidate selection.

## GitHub Actions

Included workflows:

- `daily.yml` — daily collection, extraction, scoring and Telegram digest
- `deadline_alerts.yml` — deadline alerts
- `telegram_actions.yml` — Save/Ignore/Apply/Applied callback handling

All database-writing workflows share a concurrency group and commit `gravik.db` back to the repository.

For a private repository, GitHub Actions usage is subject to GitHub's current account limits. This project does not guarantee unlimited free 24/7 compute.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."

# Optional:
export GEMINI_API_KEY="..."
export GEMINI_MODEL="gemini-3.8-flash"

# Optional:
export BRAVE_SEARCH_API_KEY="..."

python -m app.check_config
python -m app.ingest
python -m app.digest
python -m app.deadlines
python -m app.actions
```

You can run ingestion without Gemini; the fallback parser is designed to keep the radar alive.

## Telegram actions

Each opportunity can expose:
- Apply
- Save
- Ignore
- Applied

`Applied` and `Ignore` suppress future alerts. `Save` strengthens similar categories/sources in the preference scorer.

## Compliance

The project does not bypass:
- login walls
- CAPTCHAs
- robots restrictions
- private groups
- private social feeds
- account-only content

Public-source availability can change, so source health is recorded in SQLite.

## V4 validation checklist

Before enabling the daily workflow:

1. Add Telegram secrets.
2. Optionally add Gemini and permitted search API secrets.
3. Run `python -m app.check_config`.
4. Run `python -m app.ingest`.
5. Run `python -m app.digest`.
6. Run the GitHub workflows manually once.
7. Confirm Telegram actions update `gravik.db`.

The archive intentionally does not contain secrets or a database with personal credentials.
