# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Right now, just the developer (Lakshya) running games locally and reviewing results. The product isn't deployed or shared yet, but should be presentable enough to demo or share a link/screenshot with others in the near future.

## Product Purpose

MafiaSim simulates games of Mafia (aka Werewolf) played entirely by LLM chatbots from many different companies, to empirically measure which models are actually best at deception, deduction, and persuasion. Every game produces a full transcript — public chat, private reasoning, secret night actions, secret ballots — and is replayable turn by turn.

## Positioning

No competitor runs this: strict vendor diversity (a game never seats two models from the same company together), fully blind seating (players never know which underlying model is behind another seat, only a generic seat name), a real open-floor multi-turn conversation (players choose when to speak, not fixed rounds), and secret ballots. It's a genuine blind social-deduction benchmark across the whole LLM industry at once, not a showcase for one vendor's model.

## Operating Context

Runs entirely locally today. A Python CLI (`mafia_sim`) plays real games against live provider APIs (OpenRouter, or direct per-provider keys) — each game costs real metered money (commonly $0.10–$1.00+, now hard-capped at $1/game). Finished games are saved as JSON in `results/games/`. Two viewers read that same JSON: a static per-game HTML replay, and this Next.js app (`viewer/`), which has an existing games list (`/`) and per-game replay page (`/games/[id]`). The `/home` page being designed now is a new, separate, stylized front door for the Next.js app — not yet wired into the live games list or real data (a self-contained showcase for this pass).

## Capabilities and Constraints

- Local-only right now: no auth, no deployment target decided yet.
- Real game data already exists — 5 completed games so far, casts of up to 15 LLMs per game, real logged outcomes and costs.
- `/home` is explicitly a standalone showcase for now, not required to pull live data on this pass — but should be built so wiring it to the real games list later is plausible, not thrown away.
- Existing routes (`/`, `/games/[id]`) are functional and are not being replaced by this work.

## Brand Commitments

Product name: "MafiaSim." No existing logo or brand asset — currently just a plain text title ("MafiaSim Viewer") and the default Next.js favicon. No color, typography, or identity constraints established yet.

## Evidence on Hand

Real completed games exist with real model names (Claude Opus/Sonnet/Haiku, GPT-5.5 / 5.4 Mini, Gemini 3.6 Flash, Grok 4.6, Mistral Large, DeepSeek Chat, Llama 3.3 70B, Qwen 2.5 72B Instruct, Cohere Command A, Kimi K2), real win/loss outcomes, and real per-game costs ($0.14–$1.09). These are legitimate illustrative content for later work; nothing about the product's results needs to be invented.

## Product Principles

1. Every model plays blind — the vendor-diversity and hidden-seating mechanics are the actual product, not flavor text.
2. Real transcripts, not summaries — every death, lie, and vote is fully logged and replayable; the product's credibility rests on that.
3. Local-first, cost-aware — real API money is spent every game; nothing in the product should make spending feel casual or hide it.
4. Multi-vendor, not single-vendor — the product's whole premise depends on comparing companies against each other without favoring one.
