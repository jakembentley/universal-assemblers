"""
Tutorial mode for Universal Assemblers.

Provides a step-by-step guided walkthrough shown as a panel overlay.
Each step has a title, body text, and an optional condition that auto-advances
the tutorial when met (all steps can also be manually advanced with NEXT).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class TutorialStep:
    title:     str
    body:      str
    condition: Callable | None = None   # (game_state) -> bool; None = manual only


# ---------------------------------------------------------------------------
# Tutorial steps
# ---------------------------------------------------------------------------

STEPS: list[TutorialStep] = [
    TutorialStep(
        title="Welcome to Universal Assemblers",
        body=(
            "Your colony has just landed on your home planet.\n"
            "You start with a Miner Bot, Constructor Bot, Factory,\n"
            "several Power Plants, a Research Array, and one Probe ship.\n\n"
            "Press NEXT to begin the tutorial."
        ),
    ),
    TutorialStep(
        title="Selecting Planets & Entities",
        body=(
            "Click any body in the MAP PANEL (right side) to select it.\n"
            "The ENTITIES PANEL (left side) shows what is on that body.\n"
            "Click an entity type — like 'Miner Bot' — to open its detail\n"
            "view and manage its tasks.\n\n"
            "Press NEXT when ready."
        ),
    ),
    TutorialStep(
        title="Assigning Mining Tasks",
        body=(
            "Open your Miner Bot (click it in the Entities panel).\n"
            "Press '+ ADD TASK', select 'Mine', choose 'Minerals', set\n"
            "the target amount, and confirm.  Your miner will begin\n"
            "accumulating minerals automatically each in-game year.\n\n"
            "Tip: the [H] label on Bios means Harvesters only."
        ),
        condition=lambda gs: any(
            t.task_type == "mine" and t.resource == "minerals"
            for loc, btype in (gs.bot_tasks.all_keys() if gs else [])
            for t in gs.bot_tasks.get(loc, btype)
        ),
    ),
    TutorialStep(
        title="Building New Structures",
        body=(
            "Your Constructor Bot can build new facilities.\n"
            "Open the Constructor, add a 'Build' task, and choose\n"
            "a structure like 'Power Plant Solar' or 'Extractor'.\n"
            "Construction costs resources from the local planet.\n\n"
            "More power plants = faster research and production."
        ),
    ),
    TutorialStep(
        title="Manufacturing & Factory",
        body=(
            "The Factory converts raw resources into manufactured goods:\n"
            "Alloys, Electronics, Components, and more.\n"
            "Open your Factory, add a task with a recipe, and set\n"
            "the allocation percentage.\n\n"
            "Advanced structures require manufactured materials."
        ),
        condition=lambda gs: bool(
            gs and any(
                len(gs.factory_tasks.get(b.id)) > 0
                for sys in (gs.galaxy.solar_systems if gs.galaxy else [])
                for b in sys.orbital_bodies
            )
        ),
    ),
    TutorialStep(
        title="Research & Tech Tree",
        body=(
            "Open the Tech Tree using the 'TECH' button in the taskbar.\n"
            "Start researching a technology by clicking it and pressing\n"
            "'Research'.  Your Research Arrays generate research points\n"
            "each year — more arrays = faster progress.\n\n"
            "Tech unlocks new structures, ships, and abilities."
        ),
        condition=lambda gs: bool(gs and gs.tech.in_progress_ids()),
    ),
    TutorialStep(
        title="Exploring & Colonising",
        body=(
            "Your Probe can scout adjacent systems (open SHIPS panel).\n"
            "Once a system is discovered, you can send a Drop Ship to\n"
            "colonise it — a Drop Ship converts into a Constructor +\n"
            "Miner Bot on arrival at the destination planet.\n\n"
            "Build a Shipyard first to produce more ships."
        ),
    ),
    TutorialStep(
        title="Tutorial Complete!",
        body=(
            "You now know the basics of Universal Assemblers.\n\n"
            "• Mine resources → build structures → research techs\n"
            "• Expand to new systems with probes and drop ships\n"
            "• Defend against bios with Enforcer Bots\n"
            "• Ultimate goal: build a Dyson Sphere!\n\n"
            "Good luck, Commander."
        ),
    ),
]


class TutorialManager:
    """Tracks tutorial progress and determines when to advance steps."""

    def __init__(self) -> None:
        self.enabled:  bool = False
        self.step_idx: int  = 0
        self.complete: bool = False

    # ------------------------------------------------------------------

    @property
    def current_step(self) -> TutorialStep | None:
        if not self.enabled or self.complete:
            return None
        if self.step_idx < len(STEPS):
            return STEPS[self.step_idx]
        return None

    def next_step(self) -> None:
        self.step_idx += 1
        if self.step_idx >= len(STEPS):
            self.complete = True

    def tick(self, game_state) -> None:
        """Auto-advance if the current step's condition is satisfied."""
        step = self.current_step
        if step and step.condition:
            try:
                if step.condition(game_state):
                    self.next_step()
            except Exception as exc:
                import logging as _logging
                _logging.getLogger("ua.tutorial").debug(
                    "Step %d condition raised: %s", self.step_idx, exc
                )

    def skip(self) -> None:
        self.complete = True

    # ------------------------------------------------------------------
    # Serialise / deserialise (stored in game save)

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "step": self.step_idx, "complete": self.complete}

    @classmethod
    def from_dict(cls, d: dict) -> "TutorialManager":
        tm = cls()
        tm.enabled  = d.get("enabled", False)
        tm.step_idx = d.get("step", 0)
        tm.complete = d.get("complete", False)
        return tm
