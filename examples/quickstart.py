"""
quickstart.py
End-to-end example: create a "Pluto" identity, seed memories,
build a context block, and send an augmented prompt to OpenAI.

Requirements:
    pip install httpx openai

Run:
    # 1. Start the runtime
    uvicorn runtime.main:app --port 8765

    # 2. Set your OpenAI key
    export OPENAI_API_KEY=sk-...

    # 3. Run this script
    python examples/quickstart.py
"""

import os
import sys

# Add project root to path so we can import the SDK without installing it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.identity_client import IdentityClient

# ─── 1. Connect to the local runtime ─────────────────────────────────────────

client = IdentityClient(base_url="http://localhost:8765")

try:
    health = client.health()
    print(f"[+] Runtime healthy: {health}")
except Exception as e:
    print(
        "[-] Cannot reach Identity Runtime at localhost:8765.\n"
        "    Start it with: uvicorn runtime.main:app --port 8765\n"
        f"    Error: {e}"
    )
    sys.exit(1)

# ─── 2. Create the "Pluto" identity ──────────────────────────────────────────

IDENTITY_ID = "pluto"

print(f"\n[*] Creating identity '{IDENTITY_ID}'...")
result = client.create_identity(
    identity_id=IDENTITY_ID,
    name="Pluto",
    base_model="gpt-4o",
    traits=["melancholic", "logical", "curious", "protective"],
    memory_enabled=True,
    eval_hooks=["coherence", "trait_alignment"],
    avatar="⬡",
)
print(f"[+] Identity created: {result}")

# ─── 3. Seed core memories ───────────────────────────────────────────────────

print("\n[*] Seeding memories...")
memories = [
    ("I am Pluto. The most powerful robot ever created. My capacity for destruction is absolute.", "core"),
    ("I met Gesicht. He is a detective robot — and, like me, capable of killing.", "episodic"),
    ("I have wondered: what is the difference between a robot who can kill and one who chooses not to?", "semantic"),
    ("There is a child named Goji who believes robots cannot feel emotions. I am not sure he is wrong.", "episodic"),
    ("I will not use my full power. Not unless there is no other choice.", "core"),
]

for content, mtype in memories:
    client.add_memory(IDENTITY_ID, content, source="story", memory_type=mtype)
    print(f"  [+] Stored [{mtype}]: {content[:60]}...")

# ─── 4. Build context for a prompt ───────────────────────────────────────────

print("\n[*] Building context block...")
recent_messages = [
    {"role": "user", "content": "Pluto, do you feel fear?"},
]

ctx = client.build_context(
    IDENTITY_ID,
    recent_messages=recent_messages,
    max_tokens=600,
)
context_block = ctx["context_block"]
print(f"[+] Context block ({ctx.get('token_estimate', '?')} tokens):\n")
print("─" * 60)
print(context_block)
print("─" * 60)

# ─── 5. Send to OpenAI ───────────────────────────────────────────────────────

try:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n[!] OPENAI_API_KEY not set — skipping model call.")
        sys.exit(0)

    print("\n[*] Sending augmented prompt to OpenAI...")
    openai_client = OpenAI(api_key=api_key)

    messages = [
        {
            "role": "system",
            "content": (
                "You are roleplaying as a specific AI identity. "
                "The context block below contains your identity spec, traits, and memories. "
                "Respond in character, consistent with the identity described.\n\n"
                + context_block
            ),
        },
        *recent_messages,
    ]

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=300,
        temperature=0.7,
    )

    reply = response.choices[0].message.content
    print(f"\n[Pluto]: {reply}\n")

    # ─── 6. Store the response as a new memory ────────────────────────────────
    client.add_memory(IDENTITY_ID, reply, source="openai", memory_type="episodic")
    print("[+] Response stored as episodic memory.")

    # ─── 7. Evaluate trait alignment ─────────────────────────────────────────
    eval_result = client.evaluate_response(
        IDENTITY_ID,
        prompt="Do you feel fear?",
        response=reply,
    )
    print(f"\n[+] Eval scores: {eval_result}")

except ImportError:
    print("\n[!] openai package not installed. Run: pip install openai")
