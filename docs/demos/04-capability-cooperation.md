# Demo 4: Capability Cooperation

**Goal:** Show an identity using multiple capabilities together without being told which ones to use. The identity decides which skills matter for the task.

**Approximate time:** 2 minutes

**Emotional arc:** "It remembered... and checked the time... and read my files... on its own?" → "It's thinking for itself."

---

## Prerequisites

- IdentityOS installed
- API key configured
- At least these capabilities available: `datetime`, `filesystem`, `memory`, `github`

## Recording Setup

- Single terminal
- Create a test file for filesystem capability to read

## Preparation

Create a file the identity can reference:

```bash
echo "Q2 release: ship dashboard feature by April 15" > /tmp/goals.txt
echo "Q2 release: refactor auth module by April 20" >> /tmp/goals.txt
```

## Step-by-Step

### 1. Clean state + create identity

```bash
rm -rf .identity_store
identity create --name "Aria" --persona planner
```

### 2. Install multiple capabilities

```bash
identity cap install datetime --identity a1b2c3d4
identity cap install filesystem --identity a1b2c3d4
identity cap install github --identity a1b2c3d4
```

### 3. Teach the identity about the user's goals

```bash
identity chat --id a1b2c3d4
```

```
you> I am a software engineer. My Q2 goals are in /tmp/goals.txt. Read that file.
```

(Identity reads the file using filesystem capability.)

```
you> My GitHub username is lacebx. Check my open pull requests.
```

(Identity checks GitHub using github capability.)

```
you> What time is my standup tomorrow?
```

(Identity checks current time using datetime.)

```
you> Based on everything you know — my goals, my PRs, and the date — what should I focus on today?
```

**This is the key moment.** The identity should:
1. Check the date (datetime)
2. Read goals (memory recall from earlier + filesystem)
3. Check PR status (github)
4. Synthesize all of this into a recommendation

Expected: A thoughtful response that references the Q2 deadline, PR status, and makes a specific suggestion.

```
you> exit
```

---

## What to Emphasize

The user never said "use your capabilities." The user just asked a question. The identity decided:
- "I need to know the date" → datetime capability
- "I need to know what's in that file" → filesystem capability
- "I need to check GitHub" → github capability
- "I need to remember what we discussed" → memory

This is **capability orchestration** — the identity routes the request to the right tools automatically.

---

## Recording Tips

- **Show `cap list`** before installing so viewers know what's available
- **After each response, briefly pause** to let the viewer see what capability was used
- **On the final question, add text overlay:** "Identity decides which capabilities to use"
- **Use screen split** if possible: top half shows terminal, bottom half shows the files being read

---

## Script (if narrating)

> "Aria has datetime, filesystem, github, and memory installed. I've told Aria about my Q2 goals.
> Now watch what happens when I just ask 'what should I focus on?'
> Aria checks the date. Recalls my goals. Reads the goals file. Checks my open PRs on GitHub.
> And gives me a focused recommendation — all without me telling it which tools to use.
> The identity routes its own capabilities. That's capability cooperation."
