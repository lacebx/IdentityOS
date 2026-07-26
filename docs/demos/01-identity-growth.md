# Demo 1: Identity Growth

**Goal:** Show how an identity transforms from a simple chatbot into a capable assistant by installing capabilities.

**Approximate time:** 2 minutes

**Emotional arc:** "Just a chatbot" → "Oh, now it does that?" → "It's actually useful!"

---

## Prerequisites

- IdentityOS installed (`pip install -e .`)
- API key configured in `.env` (any provider)
- Ollama or cloud model running

## Recording Setup

- Screen: terminal only (full screen, dark theme)
- Font: 16pt+ so text is readable
- Crop to show only the command area
- Record at 1080p, 30fps

## Step-by-Step

### 1. Clean state

```bash
rm -rf .identity_store
```

### 2. Create a basic identity

```bash
identity create --name "Ruby" --persona assistant
```

Expected output:
```
Identity created.
  id          : a1b2c3d4
  name        : Ruby
  persona     : assistant
  snapshot_id : <uuid>
  store       : .identity_store
```

### 3. Chat without capabilities — show limitations

```bash
identity chat --id a1b2c3d4
```

Paste these messages one at a time:

```
you> What time is it?
```

Expected: Ruby says something like "I don't have access to the current time" or makes something up. This is the **before** shot.

```
you> What files are in my current directory?
```

Expected: Ruby cannot list files. Another limitation.

```
you> Check my recent GitHub activity.
```

Expected: Ruby cannot access GitHub.

Type `exit` to leave the chat.

```
you> exit
```

### 4. Install the datetime capability

```bash
identity cap list
```

Expected output shows available capabilities including `datetime`.

```bash
identity cap install datetime --identity a1b2c3d4
```

Expected output:
```
  installed: datetime -> a1b2c3d4
  skills:    1 added
```

### 5. Chat again — improvement visible

```bash
identity chat --id a1b2c3d4
```

```
you> What time is it?
```

Expected: Ruby now tells you the current time! This is the **first transformation moment**.

```
you> What files are in my current directory?
```

Expected: Still can't do this. Filesystem not installed yet.

Type `exit`.

### 6. Install more capabilities

```bash
identity cap install filesystem --identity a1b2c3d4
identity cap install github --identity a1b2c3d4
```

### 7. Chat one more time — full transformation

```bash
identity chat --id a1b2c3d4
```

```
you> What time is it?
```

Expected: Answers with current time.

```
you> Read my ~/notes.txt (create this file first if it doesn't exist)
```

Expected: Ruby reads and shows the file contents.

```
you> What's the latest issue on the IdentityOS repo?
```

Expected: Ruby queries GitHub and returns real data.

Type `exit`.

### 8. Show the installed capabilities

```bash
identity inspect --id a1b2c3d4 --dashboard
```

Expected output includes "Installed Capabilities" section listing datetime, filesystem, github.

---

## Recording Tips

- **Type slowly** so viewers can read along
- **Pause after each command** — let the output appear before typing the next one
- **Highlight the contrast** — explicitly say "before" and "after" capability installation
- **Use large terminal font** (16pt+) so mobile viewers can read
- **Add a subtle sound effect** when capabilities are installed (optional)

---

## Script (if narrating)

> "This is Ruby. Ruby is an AI identity with no special skills — just conversation.
> Watch what happens when I ask Ruby for the time... Ruby can't tell me.
> Now I'll install the datetime capability. One command.
> And just like that — Ruby knows the time. Let me add filesystem and GitHub access too.
> Now Ruby can read my files, check GitHub, and tell the time.
> That's the core idea: identities grow by installing capabilities. No retraining. No code changes."
