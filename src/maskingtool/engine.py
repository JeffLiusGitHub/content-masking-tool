"""MaskingEngine: analyze text with deny-list (+ optional NER), apply
vault-backed tokenized replacements.

Analysis runs ONCE over the combined text of a document; replacements are
applied span-aware so an entity split across spans (e.g. DOCX runs) puts
the token in the first overlapping span and blanks the rest.
"""
from __future__ import annotations

import re

from presidio_analyzer import RecognizerResult

from maskingtool.operators import apply_replacements
from maskingtool.recognizers import (
    build_denylist_recognizers,
    expand_person_name_parts,
)
from maskingtool.spans import SpannedText
from maskingtool.vault import Vault
from maskingtool.urls import find_urls
from maskingtool.recognizers import _term_regex

NER_ENTITY_MAP = {"ORGANIZATION": "ORG"}  # normalize presidio/spaCy naming
NER_ENTITIES = ["PERSON", "ORGANIZATION"]


class MaskingEngine:
    def __init__(
        self,
        deny_lists: dict[str, list[str]],
        enable_ner: bool = False,
        ner_backend: str = "spacy",
        expand_person_parts: bool = True,
        allow_terms: list[str] | None = None,
        manual_terms: list[dict[str, str]] | None = None,
    ):
        if expand_person_parts and deny_lists.get("PERSON"):
            deny_lists = {
                **deny_lists,
                "PERSON": expand_person_name_parts(deny_lists["PERSON"]),
            }
        self._recognizers = build_denylist_recognizers(deny_lists)
        self._enable_ner = enable_ner
        self._ner_backend = ner_backend
        self._ner_analyzer = None  # built lazily on first NER analysis
        self._allow_terms = allow_terms or []
        self._manual_terms = manual_terms or []

    # -- analysis ----------------------------------------------------------

    def analyze(self, text: str) -> list[RecognizerResult]:
        candidates = []
        protected = [m.span() for term in self._allow_terms if term
                     for m in re.finditer(_term_regex(term), text)]
        for item in self._manual_terms:
            for m in re.finditer(re.escape(item["term"]), text):
                candidates.append((3, RecognizerResult(item["entity_type"], m.start(), m.end(), 1.0)))
        candidates.extend((2, result) for result in find_urls(text))
        for rec in self._recognizers:
            candidates.extend((1, result) for result in rec.analyze(text, entities=rec.supported_entities))
        if self._enable_ner:
            candidates.extend((0, result) for result in self._analyze_ner(text))
        kept = []
        for priority, result in sorted(candidates, key=lambda pair: (-pair[0], -pair[1].score, pair[1].start - pair[1].end, pair[1].start)):
            # Overlapping lower-priority candidates must not fragment selected
            # entities. Explicit allows, however, protect only their own range.
            overlaps = [(r.start, r.end) for r in kept if result.start < r.end and result.end > r.start]
            if overlaps and priority != 2:
                continue
            ranges = [(result.start, result.end)]
            # Manual domain selections retain their chosen type, but must not
            # disable URL masking of the remaining scheme/path/query.
            for start, end in [*protected, *overlaps]:
                ranges = [(a, b) for left, right in ranges
                          for a, b in ((left, min(right, start)), (max(left, end), right)) if a < b]
            kept.extend(RecognizerResult(result.entity_type, a, b, result.score) for a, b in ranges)
        return sorted(kept, key=lambda r: r.start)

    def _analyze_ner(self, text: str) -> list[RecognizerResult]:
        if self._ner_analyzer is None:
            self._ner_analyzer = _build_ner_analyzer()
        raw = self._ner_analyzer.analyze(
            text=text, entities=NER_ENTITIES, language="en"
        )
        return [
            RecognizerResult(
                entity_type=NER_ENTITY_MAP.get(r.entity_type, r.entity_type),
                start=r.start,
                end=r.end,
                score=min(r.score, 0.99),  # NER must never tie with the deny-list
            )
            for r in raw
        ]

    # -- masking -----------------------------------------------------------

    def mask_text(self, text: str, vault: Vault, *, html_source=False) -> str:
        analysis_text = text
        if html_source:
            from maskingtool.markup import semantic_view
            analysis_text, offsets = semantic_view(text)
        replacements = []
        for result in self.analyze(analysis_text):
            start, end = result.start, result.end
            if html_source:
                start, end = offsets[start][0], offsets[end - 1][1]
            token = vault.get_or_create_token(text[start:end], result.entity_type)
            if html_source:
                vault.set_html_original(token, analysis_text[result.start:result.end])
            replacements.append((start, end, token))
        return apply_replacements(text, replacements)

    def mask_spanned(self, spanned: SpannedText, vault: Vault) -> list[str]:
        """Mask the combined text; return the new text for each input span.

        An entity overlapping several spans puts its token where the entity
        starts and removes the remainder from the following spans.
        """
        text = spanned.text
        results = self.analyze(text)
        tokens = {
            (r.start, r.end): vault.get_or_create_token(
                text[r.start : r.end], r.entity_type
            )
            for r in results
        }
        out: list[str] = []
        for span in spanned.spans:
            edits: list[tuple[int, int, str]] = []
            for r in results:
                ov_start = max(r.start, span.start)
                ov_end = min(r.end, span.end)
                if ov_start >= ov_end:
                    continue
                repl = tokens[(r.start, r.end)] if r.start >= span.start else ""
                edits.append((ov_start - span.start, ov_end - span.start, repl))
            out.append(apply_replacements(span.text, edits))
        return out


# -- helpers ---------------------------------------------------------------


def _resolve_overlaps(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Deterministic overlap resolution: higher score wins, then longer span,
    then earlier start. Kept results never overlap each other."""
    ranked = sorted(results, key=lambda r: (-r.score, r.start - r.end, r.start))
    kept: list[RecognizerResult] = []
    for r in ranked:
        if all(r.end <= k.start or r.start >= k.end for k in kept):
            kept.append(r)
    return sorted(kept, key=lambda r: r.start)


def _build_ner_analyzer():
    """Full Presidio AnalyzerEngine with a local spaCy model, used only when
    NER is enabled. Requires en_core_web_sm to be installed (one-time download);
    runs fully offline afterwards."""
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
    )
    nlp_engine = provider.create_engine()
    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(nlp_engine=nlp_engine, languages=["en"])
    return AnalyzerEngine(
        nlp_engine=nlp_engine, registry=registry, supported_languages=["en"]
    )
