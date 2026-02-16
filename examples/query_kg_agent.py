#!/usr/bin/env python3.10
"""
Example: Query WikiGR knowledge graph using the agent library.

Usage:
    python examples/query_kg_agent.py "Who founded OpenAI?"
    python examples/query_kg_agent.py "What is deep learning?"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from wikigr.agent import KnowledgeGraphAgent


def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/query_kg_agent.py '<question>' [db_path]")
        print("\nExamples:")
        print("  'Who founded OpenAI?'")
        print("  'What is deep learning?' data/wikigr_1k.db")
        sys.exit(1)

    question = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else "data/wikigr_30k.db"

    # Initialize agent
    agent = KnowledgeGraphAgent(db_path=db_path)

    # Query
    print(f"\n📊 Question: {question}\n")
    result = agent.query(question, max_results=10)

    # Display results
    print(f"💡 Answer:\n{result['answer']}\n")

    if result.get("entities"):
        print("🔍 Entities found:")
        for ent in result["entities"][:5]:
            print(f"  • {ent['name']} ({ent['type']})")
        print()

    if result.get("facts"):
        print("📚 Relevant facts:")
        for fact in result["facts"][:5]:
            print(f"  • {fact}")
        print()

    if result.get("sources"):
        print(f"📖 Sources: {', '.join(result['sources'][:5])}\n")

    print(f"🔧 Query type: {result['query_type']}")
    print(f"🗄️  Cypher: {result['cypher_query'][:100]}...")

    agent.close()


if __name__ == "__main__":
    main()
