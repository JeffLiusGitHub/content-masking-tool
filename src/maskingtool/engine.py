"""MaskingEngine: analyze text with deny-list (+ optional NER), apply
vault-backed tokenized replacements.

Analysis runs ONCE over the combined text of a document; replacements are
applied span-aware so an entity split across spans (e.g. DOCX runs) puts
the token in the first overlapping span and blanks the rest.
"""
from __future__ import annotations

from presidio_analyzer import RecognizerResult

from maskingtool.operators import apply_replacements
from maskingtool.recognizers import (
    DENYLIST_SCORE,
    build_denylist_recognizers,
    expand_person_name_parts,
)
from maskingtool.spans import SpannedText
from maskingtool.vault import Vault

NER_ENTITY_MAP = {"ORGANIZATION": "ORG"}  # normalize presidio/spaCy naming
NER_ENTITIES = ["PERSON", "ORGANIZATION"]


class MaskingEngine:
    def __init__(
        self,
        deny_lists: dict[str, list[str]],
        enable_ner: bool = False,
        ner_backend: str = "spacy",
        expand_person_parts: bool = True,
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

    # -- analysis ----------------------------------------------------------

    def analyze(self, text: str) -> list[RecognizerResult]:
        results: list[RecognizerResult] = []
        for rec in self._recognizers:
            results.extend(rec.analyze(text, entities=rec.supported_entities))
        if self._enable_ner:
            results.extend(self._analyze_ner(text))
        return _resolve_overlaps(results)

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

    def mask_text(self, text: str, vault: Vault) -> str:
        replacements = [
            (r.start, r.end, vault.get_or_create_token(text[r.start : r.end], r.entity_type))
            for r in self.analyze(text)
        ]
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
