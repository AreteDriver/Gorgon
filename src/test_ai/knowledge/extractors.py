"""Entity and relation extractors for knowledge graphs."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from .base import Entity, EntityType, Triple


class EntityExtractor(ABC):
    """Abstract base class for entity extraction."""

    @abstractmethod
    def extract_entities(self, text: str) -> list[Entity]:
        """Extract entities from text.

        Args:
            text: Input text

        Returns:
            List of extracted entities
        """
        pass


class RelationExtractor(ABC):
    """Abstract base class for relation extraction."""

    @abstractmethod
    def extract_relations(
        self,
        text: str,
        entities: list[Entity] | None = None,
    ) -> list[Triple]:
        """Extract relations from text.

        Args:
            text: Input text
            entities: Optional pre-extracted entities

        Returns:
            List of extracted triples
        """
        pass


class SimpleEntityExtractor(EntityExtractor):
    """Simple rule-based entity extractor.

    Uses patterns and gazetteers for basic extraction.
    """

    def __init__(
        self,
        patterns: dict[str, str] | None = None,
        gazetteer: dict[str, EntityType] | None = None,
    ):
        """Initialize simple extractor.

        Args:
            patterns: Regex patterns mapping to entity types
            gazetteer: Known entities mapping to types
        """
        self._patterns = patterns or {
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b": EntityType.PERSON,
            r"\b[A-Z][A-Z]+\b": EntityType.ORGANIZATION,
            r"\b(?:class|function|def|const|let|var)\s+(\w+)": EntityType.CODE,
        }
        self._gazetteer = gazetteer or {}

    def extract_entities(self, text: str) -> list[Entity]:
        """Extract entities using patterns and gazetteer."""
        entities = []
        seen_names = set()

        # Check gazetteer
        for name, entity_type in self._gazetteer.items():
            if name.lower() in text.lower() and name.lower() not in seen_names:
                entities.append(Entity(name=name, type=entity_type))
                seen_names.add(name.lower())

        # Apply patterns
        for pattern, entity_type in self._patterns.items():
            for match in re.finditer(pattern, text):
                # Get the matched name (use group 1 if exists, else group 0)
                name = match.group(1) if match.lastindex else match.group(0)
                if name.lower() not in seen_names:
                    entities.append(Entity(name=name, type=entity_type))
                    seen_names.add(name.lower())

        return entities


class LLMEntityExtractor(EntityExtractor, RelationExtractor):
    """LLM-based entity and relation extractor.

    Uses a language model to extract structured knowledge from text.
    """

    ENTITY_PROMPT = """Extract all named entities from the following text.

Text: {text}

For each entity, identify:
1. The entity name
2. The entity type (person, organization, location, concept, event, product, code, file, function, class)

Return as JSON array:
[{{"name": "entity name", "type": "entity type", "properties": {{}}}}]

Only output the JSON array, nothing else."""

    RELATION_PROMPT = """Extract relationships between entities from the following text.

Text: {text}

Known entities: {entities}

For each relationship found, identify:
1. Subject entity name
2. Relation type (e.g., "works_at", "located_in", "created_by", "depends_on", "calls", "inherits_from")
3. Object entity name

Return as JSON array:
[{{"subject": "entity1", "relation": "relation_type", "object": "entity2"}}]

Only output the JSON array, nothing else."""

    def __init__(
        self,
        provider: Any,
        entity_prompt: str | None = None,
        relation_prompt: str | None = None,
    ):
        """Initialize LLM extractor.

        Args:
            provider: LLM provider for extraction
            entity_prompt: Custom entity extraction prompt
            relation_prompt: Custom relation extraction prompt
        """
        self._provider = provider
        self._entity_prompt = entity_prompt or self.ENTITY_PROMPT
        self._relation_prompt = relation_prompt or self.RELATION_PROMPT

    def extract_entities(self, text: str) -> list[Entity]:
        """Extract entities using LLM."""
        from test_ai.providers import CompletionRequest

        prompt = self._entity_prompt.format(text=text)

        try:
            request = CompletionRequest(
                prompt=prompt,
                temperature=0.0,
                max_tokens=2000,
            )
            response = self._provider.complete(request)

            # Parse JSON response
            entities_data = self._parse_json_response(response.content)
            if not isinstance(entities_data, list):
                return []

            entities = []
            for item in entities_data:
                if isinstance(item, dict) and "name" in item:
                    entity_type = item.get("type", "concept")
                    try:
                        entity_type = EntityType(entity_type.lower())
                    except ValueError:
                        pass  # Graceful degradation: unrecognized entity type kept as string

                    entities.append(
                        Entity(
                            name=item["name"],
                            type=entity_type,
                            properties=item.get("properties", {}),
                        )
                    )

            return entities

        except Exception:
            return []

    def extract_relations(
        self,
        text: str,
        entities: list[Entity] | None = None,
    ) -> list[Triple]:
        """Extract relations using LLM."""
        from test_ai.providers import CompletionRequest

        # Extract entities if not provided
        if entities is None:
            entities = self.extract_entities(text)

        if not entities:
            return []

        entity_names = [e.name for e in entities]
        entity_map = {e.name.lower(): e for e in entities}

        prompt = self._relation_prompt.format(
            text=text,
            entities=", ".join(entity_names),
        )

        try:
            request = CompletionRequest(
                prompt=prompt,
                temperature=0.0,
                max_tokens=2000,
            )
            response = self._provider.complete(request)

            # Parse JSON response
            relations_data = self._parse_json_response(response.content)
            if not isinstance(relations_data, list):
                return []

            triples = []
            for item in relations_data:
                if not isinstance(item, dict):
                    continue

                subject_name = item.get("subject", "")
                relation = item.get("relation", "")
                object_name = item.get("object", "")

                if not all([subject_name, relation, object_name]):
                    continue

                # Find or create entities
                subject = entity_map.get(subject_name.lower())
                obj = entity_map.get(object_name.lower())

                if not subject:
                    subject = Entity(name=subject_name, type=EntityType.CONCEPT)
                    entity_map[subject_name.lower()] = subject

                if not obj:
                    obj = Entity(name=object_name, type=EntityType.CONCEPT)
                    entity_map[object_name.lower()] = obj

                triples.append(
                    Triple(
                        subject=subject,
                        relation=relation,
                        object=obj,
                    )
                )

            return triples

        except Exception:
            return []

    def extract_knowledge(self, text: str) -> tuple[list[Entity], list[Triple]]:
        """Extract both entities and relations.

        Args:
            text: Input text

        Returns:
            Tuple of (entities, triples)
        """
        entities = self.extract_entities(text)
        triples = self.extract_relations(text, entities)
        return entities, triples

    def _parse_json_response(self, text: str) -> Any:
        """Parse JSON from LLM response."""
        # Try to find JSON in the response
        text = text.strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass  # Non-critical fallback: direct parse failed, try extracting JSON array

        # Try to extract JSON array
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass  # Non-critical fallback: array extraction failed, try JSON object

        # Try to extract JSON object
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass  # Non-critical fallback: all JSON parse strategies exhausted

        return None


class CodeEntityExtractor(EntityExtractor):
    """Extract entities from code (classes, functions, etc.)."""

    # Patterns for different languages
    PATTERNS = {
        "python": {
            "class": r"class\s+(\w+)",
            "function": r"def\s+(\w+)",
            "import": r"(?:from\s+(\S+)\s+)?import\s+(\w+)",
            "variable": r"^(\w+)\s*=",
        },
        "javascript": {
            "class": r"class\s+(\w+)",
            "function": r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\(|(\w+)\s*=\s*(?:async\s*)?\()",
            "import": r"import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]",
        },
        "typescript": {
            "class": r"class\s+(\w+)",
            "function": r"(?:function\s+(\w+)|const\s+(\w+)\s*=|(\w+)\s*:.*?=>)",
            "interface": r"interface\s+(\w+)",
            "type": r"type\s+(\w+)",
        },
    }

    def __init__(self, language: str = "python"):
        """Initialize code extractor.

        Args:
            language: Programming language
        """
        self._language = language
        self._patterns = self.PATTERNS.get(language, self.PATTERNS["python"])

    def extract_entities(self, text: str) -> list[Entity]:
        """Extract code entities."""
        entities = []
        seen = set()

        for entity_type, pattern in self._patterns.items():
            for match in re.finditer(pattern, text, re.MULTILINE):
                # Get first non-None group
                name = next((g for g in match.groups() if g), None)
                if name and name not in seen:
                    entities.append(
                        Entity(
                            name=name,
                            type=EntityType.CODE,
                            properties={
                                "code_type": entity_type,
                                "language": self._language,
                            },
                        )
                    )
                    seen.add(name)

        return entities
