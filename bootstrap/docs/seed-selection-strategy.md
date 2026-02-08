# Seed Article Selection Strategy

**Date:** February 7, 2026
**Target:** 3,000 seed articles
**Purpose:** Initialize WikiGR with diverse, high-quality articles for expansion to 30K

---

## Executive Summary

**Strategy:** Wikipedia Category Sampling

**Approach:**
- Select **6 diverse topic categories**
- Sample **500 articles per category** = 3,000 total seeds
- Use Wikipedia Category API for automated collection
- Filter for quality and completeness
- Ensure good link connectivity

**Categories Selected:**
1. Computer Science & AI (500 articles)
2. Physics & Mathematics (500 articles)
3. Biology & Medicine (500 articles)
4. History & Social Sciences (500 articles)
5. Philosophy & Arts (500 articles)
6. Engineering & Technology (500 articles)

---

## Why Wikipedia Categories?

### Option A: Wikipedia Category Sampling ✅ **CHOSEN**

**Pros:**
- ✅ Automated collection via Category API
- ✅ Natural topic diversity
- ✅ High-quality articles (curated by Wikipedia community)
- ✅ Good link connectivity within categories
- ✅ Scalable (can expand to more categories)

**Cons:**
- ⚠️ Category trees can be deep/complex
- ⚠️ Some overlap between categories

### Option B: DBpedia SPARQL Query

**Pros:**
- Structured semantic data
- Precise filtering (e.g., by type, properties)

**Cons:**
- ❌ Requires DBpedia knowledge
- ❌ May not reflect current Wikipedia state
- ❌ More complex setup

### Option C: Manual Curation

**Pros:**
- Highest quality control
- Can cherry-pick best articles

**Cons:**
- ❌ Time-consuming (3K articles manually)
- ❌ Not scalable
- ❌ Human bias

**Decision:** **Option A (Wikipedia Categories)** - Best balance of automation, quality, and diversity

---

## Category Selection

### 1. Computer Science & AI
**Target:** 500 articles

**Primary Categories:**
- `Machine_learning` (200)
- `Artificial_intelligence` (150)
- `Computer_science` (100)
- `Programming_languages` (50)

**Example Articles:**
- Machine Learning
- Deep Learning
- Neural Network
- Natural Language Processing
- Computer Vision
- Reinforcement Learning
- Supervised Learning
- Unsupervised Learning

### 2. Physics & Mathematics
**Target:** 500 articles

**Primary Categories:**
- `Physics` (200)
- `Quantum_mechanics` (100)
- `Mathematics` (150)
- `Algebra` (50)

**Example Articles:**
- Quantum Computing
- General Relativity
- Quantum Mechanics
- Calculus
- Linear Algebra
- Thermodynamics
- Electromagnetism

### 3. Biology & Medicine
**Target:** 500 articles

**Primary Categories:**
- `Biology` (200)
- `Molecular_biology` (150)
- `Medicine` (100)
- `Genetics` (50)

**Example Articles:**
- DNA
- Cell Biology
- Evolution
- Genetics
- Neuroscience
- Biochemistry
- Molecular Biology

### 4. History & Social Sciences
**Target:** 500 articles

**Primary Categories:**
- `European_history` (200)
- `Sociology` (150)
- `Economics` (100)
- `Political_science` (50)

**Example Articles:**
- World War II
- Renaissance
- Industrial Revolution
- Democracy
- Capitalism
- Sociology
- Political Science

### 5. Philosophy & Arts
**Target:** 500 articles

**Primary Categories:**
- `Philosophy` (200)
- `Philosophy_of_mind` (100)
- `Art` (150)
- `Music` (50)

**Example Articles:**
- Philosophy
- Ethics
- Consciousness
- Epistemology
- Metaphysics
- Art History
- Classical Music

### 6. Engineering & Technology
**Target:** 500 articles

**Primary Categories:**
- `Engineering` (200)
- `Electrical_engineering` (150)
- `Mechanical_engineering` (100)
- `Civil_engineering` (50)

**Example Articles:**
- Engineering
- Electrical Engineering
- Mechanical Engineering
- Aerospace Engineering
- Software Engineering
- Robotics

---

## Collection Method

### Wikipedia Category API

**Endpoint:**
```
https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:{name}&cmlimit=500&format=json
```

**Parameters:**
- `action=query` - Query Wikipedia
- `list=categorymembers` - Get category members
- `cmtitle=Category:Machine_learning` - Category name
- `cmlimit=500` - Max results (default 10, max 500)
- `cmnamespace=0` - Only main namespace (articles)
- `format=json` - JSON response

**Pagination:**
- If >500 articles, use `cmcontinue` token
- Iterate until desired count reached

### Sample Code

```python
import requests

def fetch_category_articles(category: str, limit: int = 500) -> list[str]:
    """Fetch article titles from Wikipedia category"""
    articles = []
    continue_token = None

    while len(articles) < limit:
        params = {
            'action': 'query',
            'list': 'categorymembers',
            'cmtitle': f'Category:{category}',
            'cmlimit': min(500, limit - len(articles)),
            'cmnamespace': 0,  # Main namespace only
            'format': 'json'
        }

        if continue_token:
            params['cmcontinue'] = continue_token

        response = requests.get(
            'https://en.wikipedia.org/w/api.php',
            params=params,
            headers={'User-Agent': 'WikiGR/1.0'}
        )

        data = response.json()

        # Extract article titles
        for member in data['query']['categorymembers']:
            articles.append(member['title'])

        # Check for continuation
        if 'continue' in data and len(articles) < limit:
            continue_token = data['continue']['cmcontinue']
        else:
            break

    return articles[:limit]

# Example usage
ml_articles = fetch_category_articles('Machine_learning', limit=200)
print(f"Collected {len(ml_articles)} ML articles")
```

---

## Quality Filters

### Article Quality Criteria

**Include if:**
- ✅ Length >5,000 characters (substantial content)
- ✅ Has >10 internal links (well-connected)
- ✅ Has >3 sections (structured content)
- ✅ Not a disambiguation page
- ✅ Not a list page
- ✅ Not a redirect

**Exclude if:**
- ❌ Stub articles (<1,000 chars)
- ❌ Disambiguation pages (title contains "disambiguation")
- ❌ List pages (title starts with "List of")
- ❌ Meta pages (Wikipedia:, Help:, Template:)
- ❌ Very few links (<5)
- ❌ Very few sections (<2)

### Implementation

```python
def filter_article_quality(title: str, content: dict) -> bool:
    """Filter article by quality criteria"""

    # Exclude disambiguation and list pages
    if 'disambiguation' in title.lower():
        return False
    if title.startswith('List of'):
        return False

    # Check content length
    wikitext = content.get('wikitext', {}).get('*', '')
    if len(wikitext) < 5000:
        return False

    # Check link count
    links = content.get('links', [])
    if len(links) < 10:
        return False

    # Check section count
    sections = content.get('sections', [])
    if len(sections) < 3:
        return False

    return True
```

---

## Seed Collection Process

### Step 1: Collect Candidates (Over-sample)

For each category, collect **700 candidate articles** (40% extra):
- Category 1 (CS & AI): 700 candidates
- Category 2 (Physics & Math): 700 candidates
- Category 3 (Biology & Medicine): 700 candidates
- Category 4 (History & Social): 700 candidates
- Category 5 (Philosophy & Arts): 700 candidates
- Category 6 (Engineering & Tech): 700 candidates

**Total candidates:** 4,200

### Step 2: Fetch Metadata

For each candidate, fetch:
- Article title
- Content length (character count)
- Number of internal links
- Number of sections
- Categories

Use batch requests (50 articles at a time) for efficiency.

### Step 3: Apply Quality Filters

Filter candidates using quality criteria:
- Remove stubs (<5K chars)
- Remove poorly linked (<10 links)
- Remove shallow (<3 sections)
- Remove disambiguation/list pages

Expected pass rate: **70-80%** (4,200 → ~3,000)

### Step 4: Deduplicate

Remove duplicate titles across categories.

### Step 5: Select Top 500 per Category

Rank by quality score:
```
quality_score = (
    0.3 * (content_length / 50000) +    # Longer is better (up to 50K chars)
    0.3 * (link_count / 100) +          # More links is better (up to 100)
    0.2 * (section_count / 20) +        # More sections is better (up to 20)
    0.2 * (1.0)                          # Base quality
)
```

Select top 500 per category.

### Step 6: Save Seeds

Save to `bootstrap/data/seeds.json`:

```json
{
  "metadata": {
    "total_seeds": 3000,
    "collection_date": "2026-02-07",
    "categories": 6,
    "per_category": 500
  },
  "seeds": [
    {
      "title": "Machine Learning",
      "category": "Computer Science & AI",
      "quality_score": 0.92,
      "content_length": 45000,
      "link_count": 85,
      "section_count": 12
    },
    ...
  ]
}
```

---

## Collection Script

### File: `bootstrap/scripts/collect_seeds.py`

```python
#!/usr/bin/env python3
"""Collect 3K seed articles from Wikipedia categories"""

import requests
import json
import time
from typing import List, Dict

# Configuration
CATEGORIES = {
    'Computer Science & AI': [
        ('Machine_learning', 200),
        ('Artificial_intelligence', 150),
        ('Computer_science', 100),
        ('Programming_languages', 50),
    ],
    'Physics & Mathematics': [
        ('Physics', 200),
        ('Quantum_mechanics', 100),
        ('Mathematics', 150),
        ('Algebra', 50),
    ],
    'Biology & Medicine': [
        ('Biology', 200),
        ('Molecular_biology', 150),
        ('Medicine', 100),
        ('Genetics', 50),
    ],
    'History & Social Sciences': [
        ('European_history', 200),
        ('Sociology', 150),
        ('Economics', 100),
        ('Political_science', 50),
    ],
    'Philosophy & Arts': [
        ('Philosophy', 200),
        ('Philosophy_of_mind', 100),
        ('Art', 150),
        ('Music', 50),
    ],
    'Engineering & Technology': [
        ('Engineering', 200),
        ('Electrical_engineering', 150),
        ('Mechanical_engineering', 100),
        ('Civil_engineering', 50),
    ]
}

USER_AGENT = 'WikiGR-SeedCollector/1.0 (Educational Project)'

def fetch_category_articles(category: str, limit: int) -> List[str]:
    """Fetch article titles from Wikipedia category"""
    articles = []
    continue_token = None

    while len(articles) < limit * 1.4:  # Over-sample by 40%
        params = {
            'action': 'query',
            'list': 'categorymembers',
            'cmtitle': f'Category:{category}',
            'cmlimit': min(500, int(limit * 1.4) - len(articles)),
            'cmnamespace': 0,
            'format': 'json'
        }

        if continue_token:
            params['cmcontinue'] = continue_token

        response = requests.get(
            'https://en.wikipedia.org/w/api.php',
            params=params,
            headers={'User-Agent': USER_AGENT}
        )

        data = response.json()

        for member in data['query']['categorymembers']:
            articles.append(member['title'])

        if 'continue' in data and len(articles) < limit * 1.4:
            continue_token = data['continue']['cmcontinue']
        else:
            break

        time.sleep(0.1)  # Rate limiting

    return articles[:int(limit * 1.4)]

def fetch_article_metadata(titles: List[str]) -> List[Dict]:
    """Fetch metadata for articles in batches"""
    metadata = []

    # Batch process (50 at a time)
    for i in range(0, len(titles), 50):
        batch = titles[i:i+50]

        params = {
            'action': 'query',
            'titles': '|'.join(batch),
            'prop': 'info|links|categories',
            'pllimit': 'max',
            'cllimit': 'max',
            'format': 'json'
        }

        response = requests.get(
            'https://en.wikipedia.org/w/api.php',
            params=params,
            headers={'User-Agent': USER_AGENT}
        )

        data = response.json()

        for page_id, page_data in data['query']['pages'].items():
            if int(page_id) > 0:  # Valid page
                metadata.append({
                    'title': page_data['title'],
                    'content_length': page_data.get('length', 0),
                    'link_count': len(page_data.get('links', [])),
                    'categories': [cat['title'] for cat in page_data.get('categories', [])]
                })

        time.sleep(0.1)  # Rate limiting

    return metadata

def calculate_quality_score(meta: Dict) -> float:
    """Calculate quality score for article"""
    length_score = min(meta['content_length'] / 50000, 1.0)
    link_score = min(meta['link_count'] / 100, 1.0)

    return (
        0.4 * length_score +
        0.4 * link_score +
        0.2 * 1.0  # Base quality
    )

def filter_and_rank(metadata: List[Dict]) -> List[Dict]:
    """Filter by quality and rank"""
    # Filter
    filtered = []
    for meta in metadata:
        # Skip disambiguation and lists
        if 'disambiguation' in meta['title'].lower():
            continue
        if meta['title'].startswith('List of'):
            continue

        # Quality thresholds
        if meta['content_length'] < 5000:
            continue
        if meta['link_count'] < 10:
            continue

        # Add quality score
        meta['quality_score'] = calculate_quality_score(meta)
        filtered.append(meta)

    # Sort by quality score
    filtered.sort(key=lambda x: x['quality_score'], reverse=True)

    return filtered

def collect_seeds():
    """Main seed collection function"""
    all_seeds = []

    for category_group, subcategories in CATEGORIES.items():
        print(f"\n{'='*60}")
        print(f"Collecting: {category_group}")
        print(f"{'='*60}")

        group_seeds = []

        for subcategory, target in subcategories:
            print(f"\n  Category: {subcategory} (target: {target})")

            # Fetch candidates
            candidates = fetch_category_articles(subcategory, target)
            print(f"    Fetched {len(candidates)} candidates")

            # Fetch metadata
            metadata = fetch_article_metadata(candidates)
            print(f"    Retrieved metadata for {len(metadata)} articles")

            # Filter and rank
            filtered = filter_and_rank(metadata)
            print(f"    Filtered to {len(filtered)} quality articles")

            # Select top N
            selected = filtered[:target]
            for article in selected:
                article['category'] = category_group
            group_seeds.extend(selected)

            print(f"    Selected top {len(selected)} articles")

        # Deduplicate within group
        seen = set()
        deduplicated = []
        for seed in group_seeds:
            if seed['title'] not in seen:
                seen.add(seed['title'])
                deduplicated.append(seed)

        print(f"\n  Total for {category_group}: {len(deduplicated)} seeds")
        all_seeds.extend(deduplicated[:500])  # Cap at 500 per category

    # Final deduplication across all categories
    seen = set()
    final_seeds = []
    for seed in all_seeds:
        if seed['title'] not in seen:
            seen.add(seed['title'])
            final_seeds.append(seed)

    print(f"\n{'='*60}")
    print(f"FINAL: {len(final_seeds)} total seeds collected")
    print(f"{'='*60}")

    # Save to JSON
    output = {
        'metadata': {
            'total_seeds': len(final_seeds),
            'collection_date': '2026-02-07',
            'categories': len(CATEGORIES),
            'per_category': 500
        },
        'seeds': final_seeds
    }

    with open('bootstrap/data/seeds.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Seeds saved to: bootstrap/data/seeds.json")

if __name__ == '__main__':
    collect_seeds()
```

---

## Expected Results

### Diversity

| Category | Articles | Percentage |
|----------|----------|------------|
| Computer Science & AI | 500 | 16.7% |
| Physics & Mathematics | 500 | 16.7% |
| Biology & Medicine | 500 | 16.7% |
| History & Social Sciences | 500 | 16.7% |
| Philosophy & Arts | 500 | 16.7% |
| Engineering & Technology | 500 | 16.7% |
| **Total** | **3000** | **100%** |

### Quality Distribution

Expected quality scores:
- High (>0.8): 30% (900 articles)
- Medium (0.6-0.8): 50% (1500 articles)
- Acceptable (0.4-0.6): 20% (600 articles)

### Link Connectivity

Expected average links per article: **50-70**
- Enables 2-hop expansion to ~10K articles
- Provides good graph connectivity

---

## Validation

### Post-Collection Checks

1. **Count:** Verify exactly 3,000 seeds
2. **Diversity:** Verify ~500 per category
3. **Quality:** Spot-check 10 random articles
4. **Duplicates:** No duplicate titles
5. **Format:** Valid JSON structure

### Test Load

```python
# Load seeds
with open('bootstrap/data/seeds.json', 'r') as f:
    data = json.load(f)

seeds = data['seeds']

print(f"Total seeds: {len(seeds)}")
print(f"Categories: {data['metadata']['categories']}")

# Count by category
from collections import Counter
category_counts = Counter(s['category'] for s in seeds)
for cat, count in category_counts.items():
    print(f"  {cat}: {count} articles")

# Quality distribution
quality_scores = [s['quality_score'] for s in seeds]
print(f"\nQuality (avg): {sum(quality_scores) / len(quality_scores):.2f}")
print(f"Quality (min): {min(quality_scores):.2f}")
print(f"Quality (max): {max(quality_scores):.2f}")
```

---

## Timeline

- **Collection time:** ~2-3 hours (API calls, rate limiting)
- **Manual review:** ~30 minutes (spot-check quality)
- **Total:** ~3 hours

---

## Next Steps

1. Run `python bootstrap/scripts/collect_seeds.py`
2. Validate `bootstrap/data/seeds.json`
3. Use seeds for Phase 3 expansion testing (1K from 100 seeds)
4. Use all 3K seeds for Phase 4 expansion to 30K

---

**Prepared by:** Claude Code (Sonnet 4.5)
**Review Status:** Ready for implementation
**Decision:** ✅ Proceed with Wikipedia Category Sampling
