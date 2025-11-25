# Prompts for TalentFlow Agent

This directory contains carefully engineered prompts for the AI core. Prompts are organized by module and stage of the workflow.

## Structure
- `vacancy_analyzer.md`: Extracts pain points, KPIs, tech stack from job descriptions.
- `archetype_matcher.md`: Matches vacancy to specialist archetypes.
- `response_generator.md`: Generates personalized cover letters/responses.
- `quality_scorer.md`: Evaluates response quality and relevance.

## Usage Guidelines
- Use Claude 3.5 Sonnet or GPT-4o-mini as primary models.
- Always include vacancy text, candidate profile, and RAG context.
- Temperature: 0.3-0.5 for consistency.
- Max tokens: 2000 for analysis, 1500 for generation.

## Prompt Engineering Principles
- Chain-of-Thought (CoT) for analysis.
- Few-shot examples for high fidelity.
- JSON output for structured extraction.
- Human-like tone for responses.