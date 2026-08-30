"""بنية الخيط الذهبي | Golden thread graph (§15.1).

بنى محايدة تُغذّي الفحوص. الفصل عن نماذج قاعدة البيانات مقصود: الفحوص
منطق علمي خالص، ويجب أن تكون قابلة للتشغيل والاختبار بلا قاعدة بيانات.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Element:
    element_id: str
    element_type: str
    label: str
    detail: str | None = None
    theory_id: str | None = None


@dataclass(frozen=True, slots=True)
class Link:
    source_id: str
    target_id: str
    link_type: str


@dataclass(frozen=True, slots=True)
class VariableSpec:
    variable_id: str
    name: str
    role: str
    has_operational_definition: bool
    appears_in_title: bool
    construct_id: str | None = None


@dataclass(frozen=True, slots=True)
class InstrumentSpec:
    instrument_id: str
    name: str
    measured_variable_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MethodSpec:
    study_type: str
    design_family: str | None = None
    sampling_strategy: str | None = None
    sample_size: int | None = None
    population: str | None = None


@dataclass(slots=True)
class ThreadGraph:
    """صورة كاملة للخيط في لحظة الفحص."""

    elements: list[Element] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    variables: list[VariableSpec] = field(default_factory=list)
    instruments: list[InstrumentSpec] = field(default_factory=list)
    method: MethodSpec | None = None
    title: str = ""
    discussion_text: str = ""
    results_text: str = ""

    def by_type(self, element_type: str) -> list[Element]:
        return [e for e in self.elements if e.element_type == element_type]

    def outgoing(self, element_id: str, link_type: str | None = None) -> list[Link]:
        return [
            link for link in self.links
            if link.source_id == element_id and (link_type is None or link.link_type == link_type)
        ]

    def incoming(self, element_id: str, link_type: str | None = None) -> list[Link]:
        return [
            link for link in self.links
            if link.target_id == element_id and (link_type is None or link.link_type == link_type)
        ]

    def has_path_to_type(self, element_id: str, target_type: str, max_depth: int = 4) -> bool:
        """هل يصل هذا العنصر إلى عنصر من النوع المطلوب؟

        العمق محدود عمدًا: سلسلة طويلة جدًا بين سؤال وتحليله ليست اتصالًا
        حقيقيًا بل التفافًا.
        """
        types = {e.element_id: e.element_type for e in self.elements}
        seen = {element_id}
        frontier = [element_id]
        for _ in range(max_depth):
            nxt: list[str] = []
            for node in frontier:
                for link in self.outgoing(node):
                    if link.target_id in seen:
                        continue
                    if types.get(link.target_id) == target_type:
                        return True
                    seen.add(link.target_id)
                    nxt.append(link.target_id)
            if not nxt:
                break
            frontier = nxt
        return False
