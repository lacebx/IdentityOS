# Demo 2: ISP Installation

**Goal:** Show how a single command installs a bundle of capabilities (an Identity Skill Pack).

**Approximate time:** 1 minute

**Emotional arc:** "One command gave it all those skills?" → "This is powerful."

---

## Prerequisites

- IdentityOS installed
- API key configured
- `registry/isp/` directory populated with at least one ISP

## Recording Setup

- Terminal, full screen
- Show `identity isp list` to browse, then install

## Step-by-Step

### 1. Clean state + create identity

```bash
rm -rf .identity_store
identity create --name "Scout" --persona researcher
```

### 2. Show what's available

```bash
identity isp list
```

Expected output:
```
  Identity Skill Pack Registry
  3 packs available

  scribe               v1.0.0  Writing & communication skills
  sage                 v1.0.0  Research & analysis skills
  scout                v1.0.0  Information gathering & monitoring
```

### 3. Inspect a pack before installing

```bash
identity isp show scout
```

Expected output shows the pack details, including all the capabilities it bundles (e.g., web search, content fetching, summarization).

### 4. Install the ISP

```bash
identity isp install scout --identity a1b2c3d4
```

Expected output:
```
    installed: web (3 skills)
    installed: content (2 skills)
    installed: analysis (2 skills)

  Pack 'scout' installed — 3/3 capabilities, 7 total skills
```

### 5. Verify the skills are available

```bash
identity cap installed a1b2c3d4
```

Expected output lists all capabilities that came with the pack.

---

## Recording Tips

- **Show `isp list`** to set up the expectation of "there are bundles available"
- **Show `isp show`** to demonstrate you can inspect before buying
- **Highlight the number of skills installed** — "7 skills from one command"
- **Contrast with Demo 1** — "This is like installing datetime, filesystem, and github all at once"

---

## Script (if narrating)

> "Installing capabilities one at a time is great. But what if you want a whole skillset at once?
> That's what ISPs — Identity Skill Packs — are for.
> Let me browse what's available. I'll inspect the 'scout' pack — it bundles web research, content fetching, and analysis skills.
> One command installs all seven skills. No config. No code changes.
> Your identity just became a researcher."
