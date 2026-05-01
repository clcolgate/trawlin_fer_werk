# Job Application Automation

Fill out job application forms automatically using Claude Code + Playwright. Claude reads your resume data, navigates to the job posting, and fills in the fields — pausing to ask you on anything that needs judgment.

---

## One-Time Setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your Anthropic API key
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
Add to `~/.bashrc` or `~/.zshrc` to make it permanent.

### 3. Parse your resume
```bash
python parse_resume.py /path/to/your-resume.pdf
```
This creates `resume.json` (gitignored — stays on your machine only).

### 4. Review resume.json
Open `resume.json` and check a few key fields:
- `form_fill_preferences.salary_response` — what to type when asked for salary
- `preferences.work_arrangement` — remote / hybrid / onsite
- `personal_info.authorized_to_work` — true/false
- `personal_info.requires_sponsorship` — true/false
- `personal_info.veteran_status` / `disability_status` — update if you want

---

## Per-Application Workflow

### Step 1: Open Claude Code in this project
```bash
cd /path/to/trawlin_fer_werk
claude
```
The Playwright MCP tools load automatically from `.claude/settings.json`.

### Step 2: Give Claude the job URL
Tell Claude something like:

> "Fill out this job application: https://jobs.lever.co/company/job-id
> Use my resume.json for all data. Pause and ask me before writing any cover letter,
> salary field, or open-ended question."

### Step 3: Watch and approve
Claude will:
- Navigate to the URL in a real browser window you can see
- Fill standard fields automatically (name, contact, work history, education, skills)
- **Pause and ask you** for:
  - Cover letters
  - Salary/compensation fields (unless `salary_response` is set)
  - "Why do you want to work here?" style questions
  - Demographic/diversity questions (per your `diversity_questions_style`)
  - Anything it can't confidently answer from your data

### Step 4: Final review
Claude will stop before clicking Submit and summarize what it filled. You give final approval.

---

## Supported ATS Platforms

Works with: Greenhouse, Lever, Ashby, Workday, iCIMS, BambooHR, SmartRecruiters, Rippling, and most company-custom forms.

---

## Known Limitations

| Situation | What to do |
|-----------|-----------|
| **Resume file upload field** | Claude can't trigger the file chooser — click "Upload Resume" yourself when prompted |
| **CAPTCHA or 2FA** | Complete it in the visible browser window, then tell Claude to continue |
| **Login required** | Log in manually in the browser window before telling Claude to proceed |
| **Form detects automation** | Add `"--user-agent", "Mozilla/5.0 ..."` to args in `.claude/settings.json` |

---

## Persistent Browser Sessions (Optional)

To stay logged into job boards between Claude Code sessions, add `--user-data-dir` to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--browser", "chrome",
        "--timeout-action", "10000",
        "--timeout-navigation", "30000",
        "--user-data-dir", ".playwright-profile"
      ]
    }
  }
}
```

`.playwright-profile/` is gitignored so your session cookies stay local.

---

## Troubleshooting

**`ModuleNotFoundError`** — Run `pip install -r requirements.txt`

**`ANTHROPIC_API_KEY not set`** — Run `export ANTHROPIC_API_KEY=sk-ant-...`

**PDF text extraction returns empty** — Your PDF is image-based (scanned). Export as text from your PDF viewer, then run `python parse_resume.py resume.txt`

**Playwright can't find Chrome** — Edit `.claude/settings.json` and change `"chrome"` to `"chromium"` or `"firefox"`

**Claude skipped a field** — Check `resume.json` for that data. If missing, add it and retry.

**Want to re-parse your resume** — Run `python parse_resume.py resume.pdf --force` to overwrite `resume.json`
