#!/usr/bin/env python3
"""
Select 100 diverse seeds for 1K article expansion

Selects from 10 categories × 10 seeds = 100 total seeds
Ensures diversity for comprehensive graph coverage
"""

import json
from pathlib import Path

# 100 high-quality, diverse seeds across 10 categories
SEEDS = {
    "Computer Science & AI": [
        "Artificial intelligence",
        "Machine learning",
        "Deep learning",
        "Natural language processing",
        "Computer vision",
        "Neural network (machine learning)",
        "Python (programming language)",
        "Algorithm",
        "Data structure",
        "Software engineering",
    ],
    "Physics": [
        "Quantum mechanics",
        "General relativity",
        "Thermodynamics",
        "Electromagnetism",
        "Quantum computing",
        "Particle physics",
        "Astrophysics",
        "Optics",
        "Condensed matter physics",
        "Nuclear physics",
    ],
    "Biology & Medicine": [
        "DNA",
        "Evolution",
        "Genetics",
        "Cell biology",
        "Molecular biology",
        "Neuroscience",
        "Immunology",
        "Ecology",
        "Biochemistry",
        "Microbiology",
    ],
    "Mathematics": [
        "Calculus",
        "Linear algebra",
        "Probability theory",
        "Statistics",
        "Topology",
        "Number theory",
        "Graph theory",
        "Differential equation",
        "Complex analysis",
        "Abstract algebra",
    ],
    "History": [
        "World War II",
        "Ancient Rome",
        "Industrial Revolution",
        "Renaissance",
        "Cold War",
        "Ancient Egypt",
        "World War I",
        "American Revolution",
        "French Revolution",
        "Medieval Europe",
    ],
    "Philosophy": [
        "Philosophy",
        "Ethics",
        "Metaphysics",
        "Epistemology",
        "Logic",
        "Political philosophy",
        "Philosophy of mind",
        "Existentialism",
        "Phenomenology",
        "Philosophy of science",
    ],
    "Social Sciences": [
        "Democracy",
        "Sociology",
        "Psychology",
        "Economics",
        "Political science",
        "Anthropology",
        "Capitalism",
        "Cognitive science",
        "Game theory",
        "Behavioral economics",
    ],
    "Engineering": [
        "Electrical engineering",
        "Mechanical engineering",
        "Civil engineering",
        "Aerospace engineering",
        "Chemical engineering",
        "Software engineering",
        "Robotics",
        "Control theory",
        "Materials science",
        "Nanotechnology",
    ],
    "Chemistry": [
        "Organic chemistry",
        "Inorganic chemistry",
        "Physical chemistry",
        "Analytical chemistry",
        "Biochemistry",
        "Chemical bond",
        "Periodic table",
        "Chemical reaction",
        "Quantum chemistry",
        "Electrochemistry",
    ],
    "Arts & Culture": [
        "Art",
        "Music",
        "Literature",
        "Theatre",
        "Film",
        "Architecture",
        "Classical music",
        "Renaissance art",
        "Poetry",
        "Sculpture",
    ],
}


def main():
    print("=" * 70)
    print("1K Expansion: Seed Selection")
    print("=" * 70)

    # Flatten seeds
    all_seeds = []
    category_counts = {}

    for category, seeds in SEEDS.items():
        for seed in seeds:
            all_seeds.append({
                "title": seed,
                "category": category,
                "expansion_depth": 0
            })
        category_counts[category] = len(seeds)

    print(f"\nTotal seeds: {len(all_seeds)}")
    print("\nSeeds per category:")
    for category, count in category_counts.items():
        print(f"  {category}: {count}")

    # Save to JSON
    output = {
        "metadata": {
            "total_seeds": len(all_seeds),
            "categories": len(SEEDS),
            "per_category": 10,
            "purpose": "1K article expansion test",
            "created_date": "2026-02-08"
        },
        "seeds": all_seeds
    }

    output_path = Path("bootstrap/data/seeds_1k.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Seeds saved to: {output_path}")
    print(f"\nReady for 1K expansion:")
    print(f"  python test_1k_articles.py")


if __name__ == "__main__":
    main()
