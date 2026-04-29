#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/agent.log", mode="a"),
    ],
)


def run_agent(max_ideas: int = 10):
    from src.agents.trends_agent import TrendsAgent

    with TrendsAgent() as agent:
        report = agent.run(max_ideas=max_ideas)

    total_br = sum(len(s.trends) for s in report.sections_br)
    total_us = sum(len(s.trends) for s in report.sections_us)

    print(f"\n{'='*70}")
    print(f"  TENDÊNCIAS EM ALTA — {report.generated_at.strftime('%d/%m/%Y %H:%M')} UTC")
    print(f"{'='*70}")
    print(f"  BR: {total_br} trends  |  US: {total_us} trends  |  "
          f"Cross-platform: {len(report.cross_platform)}  |  Nicho: {len(report.niche_ideas)}")
    print(f"{'='*70}\n")

    # Brasil
    if report.sections_br:
        print("🌍 BRASIL — Top por plataforma")
        print("-" * 50)
        for section in report.sections_br:
            print(f"\n{section.emoji} {section.label}")
            for i, t in enumerate(section.trends[:5], 1):
                print(f"  {i}. {t.title[:75]}")

    # EUA
    if report.sections_us:
        print("\n\n🇺🇸 EUA — Top por plataforma")
        print("-" * 50)
        for section in report.sections_us:
            print(f"\n{section.emoji} {section.label}")
            for i, t in enumerate(section.trends[:5], 1):
                print(f"  {i}. {t.title[:75]}")

    # Cross-platform
    if report.cross_platform:
        print("\n\n🔥 CROSS-PLATFORM (2+ fontes)")
        print("-" * 50)
        for i, cp in enumerate(report.cross_platform[:10], 1):
            platforms = " + ".join(cp.platforms)
            print(f"  {i:>2}. [{cp.count}x] {cp.topic:<30} — {platforms}")

    # Niche
    if report.niche_ideas:
        print("\n\n🎯 MEU NICHO — Mecanismo Americano")
        print("-" * 50)
        for i, idea in enumerate(report.niche_ideas, 1):
            print(f"\n  {i}. {idea.main_topic}")
            print(f"     Subtema: {idea.subtopic}")
            print(f"     Região: {idea.region} | Formato: {idea.video_format.value} | "
                  f"Urgência: {idea.urgency.value} | Facilidade: {idea.ease}/10")
            print(f"     Por que: {idea.why_trending[:100]}")
            print(f"     Ângulo:  {idea.niche_angle[:100]}")
    else:
        print("\n⚠️  Nenhuma ideia de nicho gerada. Verifique OPENAI_API_KEY e os logs.")

    print(f"\n{'='*70}")
    print("  Outputs salvos em outputs/json/ e outputs/markdown/")
    print(f"{'='*70}\n")


def run_api():
    try:
        import uvicorn
        from api import app
        uvicorn.run(app, host="0.0.0.0", port=int(__import__("os").getenv("PORT", "8000")))
    except ImportError:
        print("Install fastapi and uvicorn: pip install fastapi uvicorn")
        sys.exit(1)


def show_latest():
    latest = Path("outputs/json/latest.json")
    if not latest.exists():
        print("No results yet. Run: python main.py --run")
        return
    data = json.loads(latest.read_text())
    print(f"Generated at: {data['generated_at']}")
    summary = data.get("summary", {})
    print(f"BR: {summary.get('total_br', 0)} | US: {summary.get('total_us', 0)} | "
          f"Cross-platform: {summary.get('cross_platform_topics', 0)} | "
          f"Niche ideas: {summary.get('niche_ideas', 0)}\n")

    for idea in data.get("niche_ideas", []):
        print(f"  • [{idea.get('urgency','?').upper()}] {idea['main_topic']} — {idea.get('subtopic','')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Trends Research Agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run", action="store_true", help="Run the agent")
    group.add_argument("--api", action="store_true", help="Start the API server")
    group.add_argument("--latest", action="store_true", help="Show latest results")
    parser.add_argument("--max-ideas", type=int, default=10, help="Max niche ideas to generate")
    args = parser.parse_args()

    if args.api:
        run_api()
    elif args.latest:
        show_latest()
    else:
        run_agent(max_ideas=args.max_ideas)
