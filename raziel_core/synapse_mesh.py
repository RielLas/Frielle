"""
raziel_core/synapse_mesh.py
Biological Leaky Integrate-and-Fire associative neural synapse engine for Frielle.
Shares the exact schema with Ciel's MongoDB collection 'ciel_neural_synapses'.
"""

import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple


class SynapseNeuron:
    def __init__(
        self,
        subject: str,
        remark: str,
        owner_id: str,
        canonical: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        domain: str = "general",
        synaptic_weight: float = 0.5,
        confidence: float = 0.8,
        connections: Optional[List[str]] = None,
        last_fired: float = 0.0,
        fire_count: int = 0,
        refractory_seconds: float = 600.0,
    ):
        self.subject = (subject or "").strip().lower()
        self.canonical = (canonical or self.subject).strip().lower()
        self.remark = (remark or "").strip()
        self.owner_id = str(owner_id)
        self.aliases = set([a.strip().lower() for a in (aliases or []) if a.strip()])
        self.aliases.add(self.canonical)
        self.domain = (domain or "general").strip().lower()
        self.synaptic_weight = max(0.1, min(1.0, float(synaptic_weight)))
        self.confidence = max(0.1, min(1.0, float(confidence)))
        self.connections = list(connections or [])
        self.last_fired = float(last_fired)
        self.fire_count = int(fire_count)
        self.refractory_seconds = float(refractory_seconds)
        self.membrane_potential: float = 0.0
        self.last_charge_time: float = time.time()

    def decay_potential(self, now: float, half_life_seconds: float = 120.0) -> float:
        dt = max(0.0, now - self.last_charge_time)
        if dt > 0 and self.membrane_potential > 0:
            decay_rate = math.log(2) / max(1.0, half_life_seconds)
            self.membrane_potential *= math.exp(-decay_rate * dt)
        self.last_charge_time = now
        return self.membrane_potential

    def inject_current(self, amount: float, now: float) -> float:
        self.decay_potential(now)
        self.membrane_potential = min(1.0, self.membrane_potential + amount)
        self.last_charge_time = now
        return self.membrane_potential

    def is_in_refractory(self, now: float) -> bool:
        return (now - self.last_fired) < self.refractory_seconds

    def fire(self, now: float) -> None:
        self.last_fired = now
        self.fire_count += 1
        self.membrane_potential = 0.0
        self.synaptic_weight = min(1.0, self.synaptic_weight + 0.05)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "_id": f"synapse:{self.owner_id}:{self.canonical}",
            "subject": self.subject,
            "canonical": self.canonical,
            "remark": self.remark,
            "owner_id": self.owner_id,
            "aliases": list(self.aliases),
            "domain": self.domain,
            "synaptic_weight": self.synaptic_weight,
            "confidence": self.confidence,
            "connections": self.connections,
            "last_fired": self.last_fired,
            "fire_count": self.fire_count,
            "refractory_seconds": self.refractory_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SynapseNeuron":
        return cls(
            subject=data.get("subject", ""),
            remark=data.get("remark", ""),
            owner_id=data.get("owner_id", ""),
            canonical=data.get("canonical"),
            aliases=data.get("aliases", []),
            domain=data.get("domain", "general"),
            synaptic_weight=data.get("synaptic_weight", 0.5),
            confidence=data.get("confidence", 0.8),
            connections=data.get("connections", []),
            last_fired=data.get("last_fired", 0.0),
            fire_count=data.get("fire_count", 0),
            refractory_seconds=data.get("refractory_seconds", 600.0),
        )


class SynapseMesh:
    SPIKE_THRESHOLD = 0.65
    MAX_SPIKES_PER_TURN = 2

    def __init__(self, collection: Optional[Any] = None):
        self.collection = collection
        self._neurons: Dict[str, SynapseNeuron] = {}

    def _make_key(self, canonical: str, owner_id: str) -> str:
        return f"{owner_id}:{canonical.lower().strip()}"

    def register_neuron(self, neuron: SynapseNeuron) -> None:
        key = self._make_key(neuron.canonical, neuron.owner_id)
        self._neurons[key] = neuron

    async def warm_cache(self) -> int:
        if self.collection is None:
            return 0
        try:
            cursor = self.collection.find({})
            count = 0
            async for doc in cursor:
                neuron = SynapseNeuron.from_dict(doc)
                self.register_neuron(neuron)
                count += 1
            return count
        except Exception:
            return 0

    def stimulate(self, text: str, owner_id: Optional[str] = None, now: Optional[float] = None) -> List[Tuple[SynapseNeuron, float]]:
        if not text:
            return []
        current_time = now if now is not None else time.time()
        tokens = set(re.findall(r'\b[a-zA-Z0-9_\-]{2,25}\b', text.lower()))
        if not tokens:
            return []

        activated = []
        for neuron in self._neurons.values():
            if owner_id and neuron.owner_id != str(owner_id):
                continue

            neuron.decay_potential(current_time)
            matches = tokens.intersection(neuron.aliases)
            if matches:
                current = 0.50 + (0.35 * neuron.confidence)
                score = neuron.inject_current(current, current_time)
                activated.append((neuron, score))

        return activated

    def resolve_spikes(
        self,
        text: str,
        owner_id: Optional[str] = None,
        recent_transcript: Optional[List[str]] = None,
        now: Optional[float] = None,
    ) -> List[SynapseNeuron]:
        current_time = now if now is not None else time.time()
        self.stimulate(text, owner_id=owner_id, now=current_time)

        candidates = []
        transcript_text = " ".join([str(x) for x in (recent_transcript or []) if x]).lower()

        for neuron in self._neurons.values():
            if owner_id and neuron.owner_id != str(owner_id):
                continue

            if neuron.membrane_potential >= self.SPIKE_THRESHOLD:
                if any(alias in transcript_text for alias in neuron.aliases):
                    neuron.membrane_potential = 0.2
                    continue
                if neuron.is_in_refractory(current_time):
                    continue
                candidates.append(neuron)

        if not candidates:
            return []

        candidates.sort(key=lambda n: (n.membrane_potential * n.synaptic_weight), reverse=True)
        spikes = candidates[:self.MAX_SPIKES_PER_TURN]
        for s in spikes:
            s.fire(current_time)
        return spikes
