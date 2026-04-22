#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/agent.log", mode="a"),
    ],
)

Path("logs").mkdir(exist_ok=True)


def run_agent(max_ideas: int = 10):
    from src.agents.trends_agent import TrendsAgent

    with TrendsAgent() as agent:
        ideas = agent.run(max_ideas=max_ideas)

    if ideas:
        print(f"\n✅ {len(ideas)} trend ideas generated.\n")
        print(f"{'RANK':<5} {'SCORE':<7} {'URGENCY':<10} {'TOPIC'}")
        print("-" * 70)
        for i, idea in enumerate(ideas, 1):
            print(f"{i:<5} {idea.score:<7.0f} {idea.urgency.value:<10} {idea.main_topic}")
        print("\nOutputs saved to outputs/json/ and outputs/markdown/")
    else:
        print("⚠️  No ideas generated. Check your API keys and logs.")


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
    print(f"Total ideas: {data['total']}\n")
    for i, idea in enumerate(data["ideas"], 1):
        print(f"{i}. [{idea['score']:.0f}] {idea['main_topic']} ({idea['urgency']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Trends Research Agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run", action="store_true", help="Run the agent")
    group.add_argument("--api", action="store_true", help="Start the API server")
    group.add_argument("--latest", action="store_true", help="Show latest results")
    parser.add_argument("--max-ideas", type=int, default=10, help="Max ideas to generate")
    args = parser.parse_args()

    if args.api:
        run_api()
    elif args.latest:
        show_latest()
    else:
        run_agent(max_ideas=args.max_ideas)
