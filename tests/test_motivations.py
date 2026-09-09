"""Tests for core.motivations module."""

from core.motivations import (
    Motivation,
    MotivationEngine,
    MotivationStrength,
    MotivationDomain,
)


class TestMotivation:
    def test_creation_defaults(self):
        m = Motivation(name="Test", description="Test motivation")
        assert m.id
        assert m.name == "Test"
        assert m.description == "Test motivation"
        assert m.domain == MotivationDomain.SELF
        assert m.strength == MotivationStrength.MODERATE
        assert m.expressed_as == []
        assert m.conflicts_with == []
        assert m.reinforced_by == []
        assert m.expression_count == 0

    def test_creation_with_all_fields(self):
        m = Motivation(
            name="Protect",
            description="Protect civilians",
            domain=MotivationDomain.OTHERS,
            strength=MotivationStrength.CORE,
            origin="Training",
            expressed_as=["intervene", "shield"],
            conflicts_with=["self-preservation"],
            reinforced_by=["event-123"],
        )
        assert m.name == "Protect"
        assert m.domain == MotivationDomain.OTHERS
        assert m.strength == MotivationStrength.CORE
        assert m.origin == "Training"
        assert m.expressed_as == ["intervene", "shield"]
        assert m.conflicts_with == ["self-preservation"]
        assert m.reinforced_by == ["event-123"]

    def test_express(self):
        m = Motivation(name="Test")
        assert m.expression_count == 0
        assert m.last_expressed is None
        m.express()
        assert m.expression_count == 1
        assert m.last_expressed is not None

    def test_is_core(self):
        m1 = Motivation(name="Core", strength=MotivationStrength.CORE)
        m2 = Motivation(name="Strong", strength=MotivationStrength.STRONG)
        m3 = Motivation(name="Moderate", strength=MotivationStrength.MODERATE)
        m4 = Motivation(name="Background", strength=MotivationStrength.BACKGROUND)
        assert m1.is_core()
        assert not m2.is_core()
        assert not m3.is_core()
        assert not m4.is_core()

    def test_to_prompt_line(self):
        m = Motivation(name="Truth", description="Seek truth", domain=MotivationDomain.TRUTH, strength=MotivationStrength.STRONG)
        line = m.to_prompt_line()
        assert "[TRUTH]" in line or "[truth]" in line
        assert "Truth" in line
        assert "Seek truth" in line


class TestMotivationEngine:
    def test_add_and_get(self):
        engine = MotivationEngine()
        m = Motivation(name="Test", description="Test")
        engine.add(m)
        assert engine.get(m.id) is m
        assert len(engine) == 1

    def test_remove(self):
        engine = MotivationEngine()
        m = Motivation(name="Test")
        engine.add(m)
        assert engine.remove(m.id) is True
        assert engine.get(m.id) is None
        assert engine.remove(m.id) is False

    def test_core(self):
        engine = MotivationEngine()
        m1 = Motivation(name="Core1", strength=MotivationStrength.CORE)
        m2 = Motivation(name="Strong", strength=MotivationStrength.STRONG)
        m3 = Motivation(name="Core2", strength=MotivationStrength.CORE)
        engine.add(m1)
        engine.add(m2)
        engine.add(m3)
        cores = engine.core()
        assert len(cores) == 2
        assert all(m.is_core() for m in cores)

    def test_by_domain(self):
        engine = MotivationEngine()
        m1 = Motivation(name="Self1", domain=MotivationDomain.SELF)
        m2 = Motivation(name="Others1", domain=MotivationDomain.OTHERS)
        m3 = Motivation(name="Self2", domain=MotivationDomain.SELF)
        engine.add(m1)
        engine.add(m2)
        engine.add(m3)
        self_motivations = engine.by_domain(MotivationDomain.SELF)
        assert len(self_motivations) == 2
        assert all(m.domain == MotivationDomain.SELF for m in self_motivations)

    def test_sorted_by_strength(self):
        engine = MotivationEngine()
        m1 = Motivation(name="Background", strength=MotivationStrength.BACKGROUND)
        m2 = Motivation(name="Core", strength=MotivationStrength.CORE)
        m3 = Motivation(name="Moderate", strength=MotivationStrength.MODERATE)
        m4 = Motivation(name="Strong", strength=MotivationStrength.STRONG)
        engine.add(m1)
        engine.add(m2)
        engine.add(m3)
        engine.add(m4)
        sorted_m = engine.sorted_by_strength()
        assert sorted_m[0].strength == MotivationStrength.CORE
        assert sorted_m[1].strength == MotivationStrength.STRONG
        assert sorted_m[2].strength == MotivationStrength.MODERATE
        assert sorted_m[3].strength == MotivationStrength.BACKGROUND

    def test_active_conflicts(self):
        engine = MotivationEngine()
        m1 = Motivation(name="Protect", id="m1", conflicts_with=["m2"])
        m2 = Motivation(name="Survive", id="m2", conflicts_with=["m1"])
        m3 = Motivation(name="Neutral", id="m3")
        engine.add(m1)
        engine.add(m2)
        engine.add(m3)
        conflicts = engine.active_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0][0].name == "Protect"
        assert conflicts[0][1].name == "Survive"

    def test_to_prompt_block(self):
        engine = MotivationEngine()
        m1 = Motivation(name="Truth", description="Seek truth", domain=MotivationDomain.TRUTH, strength=MotivationStrength.CORE)
        m2 = Motivation(name="Protect", description="Protect others", domain=MotivationDomain.OTHERS, strength=MotivationStrength.STRONG)
        engine.add(m1)
        engine.add(m2)
        block = engine.to_prompt_block()
        assert "Core Motivations" in block
        assert "Truth" in block
        assert "Protect" in block
        assert "[TRUTH]" in block or "[truth]" in block
        assert "[OTHERS]" in block or "[others]" in block

    def test_to_prompt_block_with_conflicts(self):
        engine = MotivationEngine()
        m1 = Motivation(name="Protect", id="m1", conflicts_with=["m2"], domain=MotivationDomain.OTHERS, strength=MotivationStrength.CORE)
        m2 = Motivation(name="Survive", id="m2", conflicts_with=["m1"], domain=MotivationDomain.SURVIVAL, strength=MotivationStrength.CORE)
        engine.add(m1)
        engine.add(m2)
        block = engine.to_prompt_block()
        assert "Active Tensions" in block
        assert "Protect <-> Survive" in block