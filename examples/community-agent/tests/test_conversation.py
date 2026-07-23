"""
Test conversation handling — chat, observe, session isolation.
"""

from identityos import IdentityObject
from .conftest import make_agent


class TestConversation:
    def test_chat_returns_reply(self):
        agent = make_agent("chat-test")
        reply = agent.chat("Hello!")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_ask_alias(self):
        agent = make_agent("ask-test")
        reply = agent.ask("What is your name?")
        assert isinstance(reply, str)

    def test_instruct_alias(self):
        agent = make_agent("instruct-test")
        reply = agent.instruct("Tell me about yourself")
        assert isinstance(reply, str)

    def test_session_isolation(self):
        agent = make_agent("session-test")
        with agent.session() as s1:
            r1 = s1.chat("Remember this: secret = 42")
        with agent.session() as s2:
            r2 = s2.chat("What secret?")
        assert isinstance(r1, str)
        assert isinstance(r2, str)


class TestObserve:
    def test_observe_facts(self):
        agent = make_agent("observe-test")
        results = agent.observe("My favorite color is blue")
        assert isinstance(results, list)
        assert len(results) >= 1
        fact = results[0]
        assert "field" in fact
        assert "value" in fact
        assert "confidence" in fact

    def test_user_facts_after_observe(self):
        agent = make_agent("facts-test")
        agent.observe("My name is Alice")
        facts = agent.user_facts()
        assert isinstance(facts, list)

    def test_observe_multiple_facts(self):
        agent = make_agent("multi-facts")
        agent.observe("My favorite color is blue and I like Python")
        facts = agent.user_facts()
        assert len(facts) >= 1
