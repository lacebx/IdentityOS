# Identity Skill Pack (ISP)

ISP is a packaging format for bundling capabilities into purpose-built skill packs. Install one pack, gain multiple capabilities.

## Available Packs

| Pack | Capabilities | Skills | Personality Shift |
|------|-------------|--------|-------------------|
| [Reviewer](packs/reviewer/manifest.json) | text, github, web, calc | 13 | Code reviewer — inspects PRs, analyzes docs, researches references |
| [Planner](packs/planner/manifest.json) | datetime, calc, text, weather | 13 | Scheduler — time-aware, weather-aware, planning-focused |
| [Architect](packs/architect/manifest.json) | filesystem, github, web, text | 16 | System designer — navigates code, researches architectures |
| [Scribe](packs/scribe/manifest.json) | filesystem, text, calc | 10 | **Librarian** — reads, indexes, analyzes your entire project |
| [Sage](packs/sage/manifest.json) | datetime, calc, web | 9 | **Oracle** — real-time facts, calculations, web knowledge |
| [Scout](packs/scout/manifest.json) | weather, github, web, datetime | 15 | **Watcher** — monitors GitHub, weather, and web intelligence |

## Install a Pack

```bash
identity isp install <pack_id> --identity <identity_id>
identity isp install planner --identity cap-demo
```

## List Available Packs

```bash
identity isp list
```

## Show Pack Details

```bash
identity isp show planner
```

## Create Your Own Pack

### 1. Structure

```
registry/isp/packs/<your-pack>/
  manifest.json
```

### 2. Manifest Format

```json
{
  "id": "my-pack",
  "name": "My Pack",
  "version": "1.0.0",
  "author": "Your Name",
  "license": "MIT",
  "description": "What this pack does",
  "capabilities": [
    {
      "id": "calc",
      "reason": "Why calc is included"
    },
    {
      "id": "datetime",
      "reason": "Why datetime is included"
    }
  ],
  "tags": ["tag1", "tag2"],
  "example_uses": [
    "What a user might ask after installing this pack",
    "Another example query"
  ]
}
```

### 3. Register in the Index

Add an entry to `registry/isp/index.json`:

```json
{
  "id": "my-pack",
  "name": "My Pack",
  "version": "1.0.0",
  "description": "What this pack does",
  "author": "Your Name",
  "capabilities": ["calc", "datetime"],
  "total_skills": 7,
  "tags": ["tag1"],
  "url": "packs/my-pack/manifest.json"
}
```

### 4. Submit a PR

Open a pull request adding:
- `registry/isp/packs/<your-pack>/manifest.json`
- An entry in `registry/isp/index.json`

## Publishing Checklist

- [ ] Pack id is unique and kebab-case
- [ ] All referenced capabilities exist in `registry/capabilities/index.json`
- [ ] `total_skills` matches the sum of skills from all referenced capabilities
- [ ] `example_uses` shows realistic user queries
- [ ] Tags help users discover your pack
