# Final Submission Checklist

Submission form: https://forms.gle/cD7fCnPnkdVm2sH78 — **one submission only, deadline Sep 29.**

## Build deliverables
- [ ] GitHub repository public and linkable (clean, documented code)
- [ ] README includes the explicit "How Hindsight memory is used" section
- [ ] Demo video: 2–5 min, 1080p, screen recording with voiceover, **public on YouTube** (never a Google Drive link)
- [ ] Live project demo ready (backend + hindsight-api + seeded data verified before presenting)

## Per-member content deliverables (every team member)
- [ ] 1 Article (800–1,500 words) published and public: Medium / Dev.to / Hashnode / Substack / LinkedIn Article
- [ ] 1 Social post (LinkedIn) promoting the article — published and public
- [ ] Articles/social must NOT mention the hackathon anywhere (title, body, hashtags) — disqualified otherwise

## Reddit
- [ ] Article submitted as a Link post on one of: r/llmdevs, r/sideproject, r/aiagents, r/aimemory

## Form fields (paste-ready)
- [ ] Email ID
- [ ] Phone Number
- [ ] Team Name (as used during registration)
- [ ] Team Members (full names of all members)
- [ ] GitHub Repository link
- [ ] Social Media Post on LinkedIn (URL)
- [ ] Article link (URL)
- [ ] Video Link (URL)
- [ ] Reddit Post Link (URL)
- [ ] Feedback

## Final-hour triage order (if time runs out)
1. Record and upload the demo video (biggest scoring gap if missing)
2. Verify the live demo end-to-end (seed + before/after toggle)
3. Publish articles + social posts
4. Submit the form with all links

## Pre-demo checks
- [ ] `hindsight-api` running on :8888, `uvicorn app.main:app` on :8000
- [ ] `POST /seed` called once (idempotent afterwards)
- [ ] Memory ON/OFF toggle + demo scenario button tested
- [ ] Hindsight "up" dot green in the top bar
