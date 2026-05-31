# WHAT

A simulation-driven strategy game where you begin in a paleolithic cave with only **embers** and a **spring**. Invent everything else in natural language — bone tools, smoke vents, strange leaps — and bend history along a path that may never reach our modern world.

## Prerequisites

- **Python 3.12** + [Poetry](https://python-poetry.org/)
- **Node.js 18+** + [Yarn](https://yarnpkg.com/) (for Lambda deploy)
- **OpenAI API key** (for in-game invention interpretation)

## Quick start

```bash
make setup
# Edit .env — set OPENAI_API_KEY

make dev
# Open http://127.0.0.1:5000
```

API docs: http://127.0.0.1:8000/docs

### Offline demo (no LLM)

```bash
make demo
```

### Tests

```bash
make test
```

## How it works

- **Paleolithic start** — one cave, two fixtures (fire, spring), survival resources (warmth, water, food, materials, knowledge)
- **Speculative invention** — if an idea *seems* like it could work in the fiction, the bench and Invent page lean toward letting you try; strict historical accuracy is not the gate
- **Novel compounds** — successful experiments can isolate new substances that enter your material stockpile for later combinations
- **Natural language inventions** — LLM maps ideas to era-appropriate capabilities
- **Alternate history** — high `uncertainty` and anachronistic tags increase `path_divergence`; the world may diverge from our timeline
- **Deterministic simulation** — same seed and actions yield the same outcomes

Hard constraints: player names are display-only; mechanics use the capability system; the LLM proposes but does not mutate world state.

## Deploy to AWS Lambda

See previous Serverless setup in `serverless.yml`. Use `yarn deploy:dev` with env vars set. Note: game saves on Lambda are ephemeral (`/tmp`).

## Project layout

```
what/
├── data/capabilities.yaml           # future-era keys
├── data/capabilities_paleolithic.yaml
├── src/civsim/                      # simulation core
├── api/                             # FastAPI
├── web/                             # Flask UI
└── Makefile
```
