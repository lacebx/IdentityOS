# Identity Skill Pack (ISP)

ISP is a packaging format for bundling capabilities into purpose-built skill packs. Install one pack, gain multiple capabilities.

## Available Packs

| Pack | Capabilities | Skills | Use Case |
|------|-------------|--------|----------|
| [Reviewer](packs/reviewer/manifest.json) | text, github, web, calc | 13 | Code review, PR inspection, document analysis |
| [Planner](packs/planner/manifest.json) | datetime, calc, text, weather | 13 | Scheduling, time management, weather-aware planning |
| [Architect](packs/architect/manifest.json) | filesystem, github, web, text | 16 | System design, code navigation, architecture research |

## Install a Pack

```bash
python tools/identity isp install <pack_id> --identity <identity_id>
python tools/identity isp install planner --identity cap-demo
```

## List Available Packs

```bash
python tools/identity isp list
```

## Show Pack Details

```bash
python tools/identity isp show planner
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
