#!/usr/bin/env python3
"""Evaluate semantic relationship quality in the knowledge graph."""

import kuzu


def evaluate_relationships(db_path: str = "data/wikigr_30k.db"):
    """Check what semantic relations were actually extracted."""
    db = kuzu.Database(db_path, read_only=True)
    conn = kuzu.Connection(db)

    print("=" * 80)
    print("RELATIONSHIP QUALITY EVALUATION")
    print("=" * 80)
    print()

    # Get distribution of relation types
    print("Top 30 Relation Types by Frequency:")
    print("-" * 80)

    r = conn.execute("""
        MATCH ()-[r:ENTITY_RELATION]->()
        RETURN r.relation AS relation_type, COUNT(*) AS count
        ORDER BY count DESC
        LIMIT 30
    """)

    df = r.get_as_df()
    total_relations = df["count"].sum()

    for idx, row in df.iterrows():
        rel_type = row["relation_type"]
        count = row["count"]
        percentage = (count / total_relations) * 100
        print(f"{idx+1:2}. {rel_type:30} {count:6,} ({percentage:5.2f}%)")

    print()
    print(f"Total relations shown: {df['count'].sum():,} / {total_relations:,}")
    print()

    # Get total count of all relations
    r_total = conn.execute("""
        MATCH ()-[r:ENTITY_RELATION]->()
        RETURN COUNT(*) AS total
    """)
    total = r_total.get_as_df().iloc[0]["total"]
    print(f"Total ENTITY_RELATION edges: {total:,}")
    print()

    # Check for generic vs specific relations
    print("=" * 80)
    print("ANALYSIS: Generic vs Specific Relations")
    print("=" * 80)
    print()

    generic = ["related_to", "associated_with", "linked_to", "connected_to"]
    specific = [
        "founded",
        "invented",
        "discovered",
        "developed",
        "created",
        "led",
        "directed",
        "authored",
        "fought_in",
        "participated_in",
    ]

    generic_count = df[df["relation_type"].isin(generic)]["count"].sum()
    specific_count = df[df["relation_type"].isin(specific)]["count"].sum()

    print(
        f"Generic relations (related_to, etc.): {generic_count:,} ({generic_count/total*100:.2f}%)"
    )
    print(
        f"Specific relations (founded, etc.): {specific_count:,} ({specific_count/total*100:.2f}%)"
    )
    print()

    if generic_count > specific_count:
        print("⚠️  WARNING: Too many generic relations!")
        print("   The LLM prompt needs refinement to extract more specific verbs.")
    else:
        print("✅ GOOD: More specific relations than generic.")
    print()

    # Sample some actual relationships
    print("=" * 80)
    print("SAMPLE RELATIONSHIPS")
    print("=" * 80)
    print()

    for rel_type in ["founded", "invented", "discovered", "developed", "created"]:
        r_sample = conn.execute(f"""
            MATCH (a)-[r:ENTITY_RELATION {{relation: '{rel_type}'}}]->(b)
            RETURN a.name AS from_entity, b.name AS to_entity, r.context AS context
            LIMIT 3
        """)
        sample_df = r_sample.get_as_df()

        if not sample_df.empty:
            print(f"{rel_type.upper()}:")
            for _, row in sample_df.iterrows():
                context = (
                    row["context"][:60] + "..." if len(row["context"]) > 60 else row["context"]
                )
                print(f"  • {row['from_entity']} → {row['to_entity']}")
                print(f"    Context: {context}")
            print()

    conn.close()


if __name__ == "__main__":
    evaluate_relationships()
