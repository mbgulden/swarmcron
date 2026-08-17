"""examples/01_ai_agent_swarm_pipeline.py

Demonstrates a complete 4-stage autonomous AI agent pipeline orchestrated with SwarmCron:
  Stage 1: fetch-market-data (Scraper agent)
  Stage 2: embed-and-index (Vector embedding agent, depends on Stage 1)
  Stage 3: generate-summary-report (LLM synthesis agent, depends on Stage 2)
  Stage 4: dispatch-alerts (Notification agent, depends on Stage 3)

Features demonstrated:
  - Strict DAG dependency ordering (tasks fail closed if upstream fails)
  - Structured machine execution receipts (CronRunReceipt) with execution duration and exit codes
  - Self-healing recovery replays (recover)
  - Zero external dependencies
"""

import sys
import tempfile
from pathlib import Path
from swarmcron import SwarmCronRegistry, SwarmCronTask, DependencyNotSatisfiedError


def main() -> None:
    print("=" * 70)
    print("🤖 SwarmCron Example: 4-Stage Autonomous AI Agent Pipeline")
    print("=" * 70)

    # Use a temporary store for demonstration
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "agent_swarm_tasks.json"
        registry = SwarmCronRegistry(path=store_path)

        # 1. Define and register pipeline tasks
        tasks = [
            SwarmCronTask(
                id="fetch-market-data",
                name="Stage 1: Financial & Sentiment Data Ingestion",
                schedule="*/15 * * * *",
                command=[sys.executable, "-c", "print('✅ [Ingest] Downloaded 1,420 ticker signals')"],
                tags=["agent:scraper", "priority:high"],
                group="data-pipeline",
            ),
            SwarmCronTask(
                id="embed-and-index",
                name="Stage 2: Vector Embedding & Knowledge Graph Indexing",
                schedule="*/15 * * * *",
                command=[sys.executable, "-c", "print('✅ [Embed] Computed 1,420 vectors, indexed into graph')"],
                depends_on=["fetch-market-data"],
                tags=["agent:vectorizer"],
                group="data-pipeline",
            ),
            SwarmCronTask(
                id="generate-summary-report",
                name="Stage 3: LLM Executive Briefing Synthesis",
                schedule="*/15 * * * *",
                command=[sys.executable, "-c", "print('✅ [LLM] Formatted executive briefing (24 key insights)')"],
                depends_on=["embed-and-index"],
                tags=["agent:analyst"],
                group="data-pipeline",
            ),
            SwarmCronTask(
                id="dispatch-alerts",
                name="Stage 4: Multi-Channel Alert & Slack Dispatch",
                schedule="*/15 * * * *",
                command=[sys.executable, "-c", "print('✅ [Alerts] Dispatched briefing to #exec-swarm channel')"],
                depends_on=["generate-summary-report"],
                tags=["agent:notifier"],
                group="data-pipeline",
            ),
        ]

        print("\n📝 1. Registering Swarm Tasks...")
        for task in tasks:
            registry.register(task)
            print(f"  • Registered: {task.id} (depends on: {task.depends_on or 'None'})")

        # 2. Demonstrate DAG safety: Attempting to run Stage 4 before Stage 1
        print("\n🔒 2. Testing DAG Safety: Attempting to run Stage 4 directly...")
        try:
            registry.mutate("dispatch-alerts", "run", enforce_dependencies=True)
            print("  ❌ ERROR: Task ran when it should have been blocked!")
        except DependencyNotSatisfiedError as exc:
            print(f"  🛡️ Upstream Guard Blocked Run as expected:\n     -> {exc}")

        # 3. Execute Pipeline sequentially in DAG order
        print("\n🚀 3. Executing Swarm Pipeline Sequentially...")
        for task in tasks:
            result = registry.mutate(task.id, "run", enforce_dependencies=True)
            rc = result["receipt"]
            print(f"  [{rc['status'].upper()}] {task.id}")
            print(f"    - Output:   {rc['stdout'].strip()}")
            print(f"    - Duration: {rc['duration_ms']:.2f}ms | Exit: {rc['exit_code']}")

        # 4. Demonstrate Recovery Replay
        print("\n🔄 4. Demonstrating Self-Healing Replay Recovery...")
        rec_result = registry.mutate("fetch-market-data", "recover", max_retries=2)
        print(f"  • Recovery success: {rec_result['success']}")
        print(f"  • Replays executed: {rec_result['replays_count']}")

        print("\n" + "=" * 70)
        print("🎉 Pipeline completed with verified machine receipts!")
        print("=" * 70)


if __name__ == "__main__":
    main()
