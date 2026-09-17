"""Natural Language Interface for Browser Capability.

Provides high-level commands for common web tasks:
- check_gmail(n=5) - Get and summarize latest n emails
- search_and_summarize(query, n=3) - Search and summarize top results
- navigate_and_extract(url, instruction) - Navigate and extract specific info
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from .session import ensure_session, close_session
from .url_policy import validate_navigation_url


@dataclass
class EmailSummary:
    """Summary of a single email."""
    sender: str
    subject: str
    time: str
    snippet: str
    is_unread: bool = False


@dataclass
class NLResult:
    """Result of a natural language command."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    summary: str = ""


class BrowserNLInterface:
    """Natural language interface for browser operations."""

    def __init__(self, browser_capability):
        self.browser = browser_capability
        self._identity_id = browser_capability._identity_id
        self._storage_root = browser_capability._storage_root
        self._headless = browser_capability._headless
        self._allow_private_network = browser_capability._allow_private_network
        self._browser_type = browser_capability._browser_type
        self._user_profile_dir = browser_capability._user_profile_dir

    def _get_session_state(self):
        """Get the session state for this identity."""
        from .session import get_session
        return get_session(
            self._identity_id,
            storage_root=self._storage_root,
            browser_type=self._browser_type,
            user_profile_dir=self._user_profile_dir,
        )

    def check_gmail(self, n: int = 5, account: str = "primary") -> NLResult:
        """Check Gmail and return summary of latest n emails.

        Args:
            n: Number of latest emails to fetch (default 5)
            account: Which account to check (default "primary")

        Returns:
            NLResult with list of EmailSummary objects
        """
        try:
            # Open Gmail inbox
            result = self.browser.call("browser.open", url="https://mail.google.com/mail/u/0/#inbox")
            if not result.success:
                return NLResult(success=False, error=f"Failed to open Gmail: {result.error}")

            # Wait for page to load
            self.browser.call("browser.wait", ms=8000)

            # Take snapshot to get emails
            snapshot = self.browser.call("browser.snapshot")
            if not snapshot.success:
                return NLResult(success=False, error="Failed to snapshot Gmail page")

            # Parse emails from snapshot
            emails = self._parse_gmail_emails(snapshot.data.get("text", ""), n)

            # Create summary
            summary_lines = [f"Found {len(emails)} emails in {account} inbox:"]
            for i, email in enumerate(emails, 1):
                unread_marker = "🔵 " if email.is_unread else ""
                summary_lines.append(
                    f"  {i}. {unread_marker}{email.time} - {email.sender}: {email.subject}"
                )
                summary_lines.append(f"     {email.snippet[:100]}...")

            return NLResult(
                success=True,
                data=emails,
                summary="\n".join(summary_lines)
            )

        except Exception as e:
            return NLResult(success=False, error=str(e))

    def _parse_gmail_emails(self, text: str, n: int) -> list[EmailSummary]:
        """Parse email list from Gmail page text (compressed single-line format)."""
        emails = []

        # Gmail compresses everything into a single line with zero-width spaces (͏)
        # Find all time patterns and extract surrounding context
        # Pattern: "H:MM AM/PM Sender Subject - snippet"

        # Find all time patterns with surrounding context
        time_pattern = re.compile(r'(\d{1,2}:\d{2}\s*[AP]M)\s+([^‌]{1,300}?)(?:\s*-\s*|\s{2,}|$)')
        # Alternative: find all time patterns and extract surrounding context
        time_positions = [(m.start(), m.group(1)) for m in re.finditer(r'(\d{1,2}:\d{2}\s*[AP]M)', text)]

        if not time_positions:
            return []

        for i, (pos, time_str) in enumerate(time_positions):
            # Extract context after the time (up to next time or 300 chars)
            start = pos
            end = time_positions[i + 1][0] if i + 1 < len(time_positions) else min(pos + 300, len(text))
            context = text[start:end].strip()

            # Clean up zero-width spaces and other formatting
            context = context.replace('͏', ' ').replace('\u200c', ' ').replace('\u200b', ' ')
            context = re.sub(r'\s+', ' ', context)

            # Extract email info: "TIME Sender Subject - snippet"
            # Pattern: "H:MM AM/PM Sender Subject - snippet"
            time_match = re.match(r'(\d{1,2}:\d{2}\s*[AP]M)\s+(.+)', context)
            if not time_match:
                continue

            time_str = time_match.group(1)
            rest = time_match.group(2).strip()

            # Split on " - " to separate sender/subject from snippet
            if " - " in rest:
                sender_subject, snippet = rest.split(" - ", 1)
            else:
                sender_subject = rest
                snippet = ""

            # Extract sender and subject
            # Format: "Sender Subject text" or "Sender: Subject text"
            words = sender_subject.split()
            if len(words) >= 3:
                sender = " ".join(words[:2])
                subject = " ".join(words[2:])
            elif len(words) == 2:
                sender = words[0]
                subject = words[1]
            else:
                sender = words[0] if words else "Unknown"
                subject = sender_subject

            email = EmailSummary(
                sender=sender,
                subject=subject,
                time=time_str,
                snippet=snippet.strip(),
                is_unread=False
            )
            emails.append(email)

            if len(emails) >= n:
                break

        return emails

    def search_and_summarize(self, query: str, n: int = 3) -> NLResult:
        """Search the web and summarize top n results.

        Args:
            query: Search query
            n: Number of results to summarize (default 3)

        Returns:
            NLResult with search results and summary
        """
        try:
            # Search
            result = self.browser.call("browser.search", query=query, task=query, max_results=n)
            if not result.success:
                return NLResult(success=False, error=f"Search failed: {result.error}")

            results = result.data.get("recommended", result.data.get("results", []))
            top_results = results[:n]

            # Open each result and extract content
            summaries = []
            for i, result_item in enumerate(top_results, 1):
                url = result_item.get("url")
                if not url:
                    continue

                open_result = self.browser.call("browser.open", url=url)
                if not open_result.success:
                    continue

                self.browser.call("browser.wait", ms=3000)
                snapshot = self.browser.call("browser.snapshot")

                if snapshot.success:
                    text = snapshot.data.get("text", "")
                    # Extract meaningful content (first 500 chars)
                    content = text[:500].strip()
                    summaries.append({
                        "rank": i,
                        "title": result_item.get("title", "No title"),
                        "url": url,
                        "score": result_item.get("score", 0),
                        "useful": result_item.get("useful", False),
                        "summary": content
                    })

            summary_text = f"Found {len(summaries)} relevant results for '{query}':\n"
            for s in summaries:
                summary_text += f"\n  {s['rank']}. {s['title']} ({s['url']})"
                summary_text += f"\n     Score: {s['score']:.2f}, Useful: {s['useful']}"
                summary_text += f"\n     {s['summary'][:200]}..."

            return NLResult(
                success=True,
                data=summaries,
                summary=summary_text
            )

        except Exception as e:
            return NLResult(success=False, error=str(e))

    def navigate_and_extract(self, url: str, instruction: str) -> NLResult:
        """Navigate to URL and extract information based on instruction.

        Args:
            url: URL to navigate to
            instruction: Natural language instruction for what to extract

        Returns:
            NLResult with extracted information
        """
        try:
            # Validate URL
            validated_url = validate_navigation_url(
                url,
                allow_private_network=self._allow_private_network
            )

            # Open URL
            result = self.browser.call("browser.open", url=validated_url)
            if not result.success:
                return NLResult(success=False, error=f"Failed to open URL: {result.error}")

            self.browser.call("browser.wait", ms=3000)

            # Take snapshot
            snapshot = self.browser.call("browser.snapshot")
            if not snapshot.success:
                return NLResult(success=False, error="Failed to snapshot page")

            text = snapshot.data.get("text", "")

            # Extract based on instruction (simple keyword-based extraction)
            extracted = self._extract_by_instruction(text, instruction)

            return NLResult(
                success=True,
                data={"url": validated_url, "extracted": extracted, "full_text": text[:2000]},
                summary=f"Extracted from {validated_url}: {extracted[:200]}..."
            )

        except Exception as e:
            return NLResult(success=False, error=str(e))

    def _extract_by_instruction(self, text: str, instruction: str) -> str:
        """Extract relevant information based on natural language instruction."""
        instruction_lower = instruction.lower()

        # Simple keyword-based extraction
        if "summary" in instruction_lower or "summarize" in instruction_lower:
            # Return first 500 chars as summary
            return text[:500].strip()

        if "email" in instruction_lower or "contact" in instruction_lower:
            # Extract email addresses
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
            return ", ".join(set(emails))

        if "link" in instruction_lower or "url" in instruction_lower:
            # Extract URLs
            urls = re.findall(r'https?://[^\s]+', text)
            return ", ".join(set(urls))

        if "price" in instruction_lower or "cost" in instruction_lower:
            # Extract prices
            prices = re.findall(r'\$[\d,]+\.?\d*', text)
            return ", ".join(set(prices))

        if "phone" in instruction_lower:
            # Extract phone numbers
            phones = re.findall(r'[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}', text)
            return ", ".join(set(phones))

        # Default: return first 500 chars
        return text[:500].strip()


def create_nl_interface(browser_capability) -> BrowserNLInterface:
    """Factory function to create NL interface for a browser capability."""
    return BrowserNLInterface(browser_capability)