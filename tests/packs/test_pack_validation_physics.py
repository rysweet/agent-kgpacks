"""Physics-expert pack validation tests.

Tests complete pack validation including:
- Manifest schema validation
- Database integrity checks
- Entity/relationship count validation
- Pack size calculations
- Tarball creation and extraction
"""

import json
import tarfile
from pathlib import Path

import pytest

# ============================================================================
# Manifest Schema Validation
# ============================================================================


def test_physics_pack_manifest_exists(physics_pack_path: Path):
    """Verify physics-expert pack has manifest.json."""
    manifest_path = physics_pack_path / "manifest.json"
    assert manifest_path.exists(), "manifest.json not found in pack"


def test_physics_pack_manifest_valid_json(physics_pack_path: Path):
    """Verify manifest.json is valid JSON."""
    manifest_path = physics_pack_path / "manifest.json"

    with open(manifest_path) as f:
        data = json.load(f)  # Should not raise JSONDecodeError

    assert isinstance(data, dict)


def test_physics_pack_manifest_has_required_fields(physics_pack_path: Path):
    """Verify manifest has all required fields."""
    from wikigr.packs.manifest import PackManifest

    manifest_path = physics_pack_path / "manifest.json"
    manifest = PackManifest.load(manifest_path)

    # Required fields
    assert manifest.name == "physics-expert"
    assert manifest.version
    assert manifest.description
    assert manifest.created
    assert manifest.license


def test_physics_pack_manifest_metadata(physics_pack_path: Path):
    """Verify pack metadata matches documentation."""
    from wikigr.packs.manifest import PackManifest

    manifest_path = physics_pack_path / "manifest.json"
    manifest = PackManifest.load(manifest_path)

    # Check version format (semantic versioning)
    import re

    semver_pattern = r"^\d+\.\d+\.\d+$"
    assert re.match(
        semver_pattern, manifest.version
    ), f"Version '{manifest.version}' doesn't follow semantic versioning"

    # Check license is CC BY-SA 3.0 (Wikipedia content)
    assert "CC BY-SA" in manifest.license


# ============================================================================
# Database Integrity Checks
# ============================================================================


def test_physics_pack_database_exists(physics_pack_path: Path):
    """Verify pack.db exists."""
    db_path = physics_pack_path / "pack.db"
    assert db_path.exists(), "pack.db not found"


def test_physics_pack_database_not_empty(physics_pack_path: Path):
    """Verify pack.db is not empty."""
    db_path = physics_pack_path / "pack.db"
    assert db_path.stat().st_size > 0, "pack.db is empty"


def test_physics_pack_database_is_kuzu(physics_pack_path: Path):
    """Verify pack.db is a valid Kuzu database."""
    import kuzu

    db_path = physics_pack_path / "pack.db"

    try:
        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)
        # Try a simple query
        result = conn.execute("MATCH (n) RETURN count(n) as count LIMIT 1")
        assert result is not None
    except Exception as e:
        pytest.fail(f"pack.db is not a valid Kuzu database: {e}")


def test_physics_pack_database_has_expected_schema(physics_pack_path: Path):
    """Verify database has expected node and relationship types."""
    import kuzu

    db_path = physics_pack_path / "pack.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    # Check for Article nodes
    result = conn.execute("MATCH (a:Article) RETURN count(a) as count")
    article_count = result.get_as_df().iloc[0]["count"]
    assert article_count > 0, "No Article nodes found"

    # Check for Entity nodes
    result = conn.execute("MATCH (e:Entity) RETURN count(e) as count")
    entity_count = result.get_as_df().iloc[0]["count"]
    assert entity_count > 0, "No Entity nodes found"


# ============================================================================
# Entity/Relationship Count Validation
# ============================================================================


def test_physics_pack_has_expected_article_count(physics_pack_path: Path):
    """Verify pack has ~5,247 articles as documented."""
    import kuzu

    db_path = physics_pack_path / "pack.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    result = conn.execute("MATCH (a:Article) RETURN count(a) as count")
    article_count = result.get_as_df().iloc[0]["count"]

    # Allow 10% variance from documented 5,247
    expected = 5247
    tolerance = 0.10
    min_count = int(expected * (1 - tolerance))
    max_count = int(expected * (1 + tolerance))

    assert (
        min_count <= article_count <= max_count
    ), f"Article count {article_count} outside expected range [{min_count}, {max_count}]"


def test_physics_pack_has_expected_entity_count(physics_pack_path: Path):
    """Verify pack has ~14,382 entities as documented."""
    import kuzu

    db_path = physics_pack_path / "pack.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    result = conn.execute("MATCH (e:Entity) RETURN count(e) as count")
    entity_count = result.get_as_df().iloc[0]["count"]

    # Allow 10% variance from documented 14,382
    expected = 14382
    tolerance = 0.10
    min_count = int(expected * (1 - tolerance))
    max_count = int(expected * (1 + tolerance))

    assert (
        min_count <= entity_count <= max_count
    ), f"Entity count {entity_count} outside expected range [{min_count}, {max_count}]"


def test_physics_pack_has_expected_relationship_count(physics_pack_path: Path):
    """Verify pack has ~23,198 relationships as documented."""
    import kuzu

    db_path = physics_pack_path / "pack.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    result = conn.execute("MATCH ()-[r]->() RETURN count(r) as count")
    rel_count = result.get_as_df().iloc[0]["count"]

    # Allow 10% variance from documented 23,198
    expected = 23198
    tolerance = 0.10
    min_count = int(expected * (1 - tolerance))
    max_count = int(expected * (1 + tolerance))

    assert (
        min_count <= rel_count <= max_count
    ), f"Relationship count {rel_count} outside expected range [{min_count}, {max_count}]"


# ============================================================================
# Pack Size Validation
# ============================================================================


def test_physics_pack_size_within_expected_range(physics_pack_path: Path):
    """Verify uncompressed pack size is ~1.2 GB as documented."""

    def get_directory_size(path: Path) -> int:
        """Calculate total size of directory in bytes."""
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total

    size_bytes = get_directory_size(physics_pack_path)
    size_mb = size_bytes / (1024 * 1024)

    # Allow 20% variance from documented 1,200 MB
    expected_mb = 1200
    tolerance = 0.20
    min_mb = expected_mb * (1 - tolerance)  # 960 MB
    max_mb = expected_mb * (1 + tolerance)  # 1440 MB

    assert (
        min_mb <= size_mb <= max_mb
    ), f"Pack size {size_mb:.0f} MB outside expected range [{min_mb:.0f}, {max_mb:.0f}] MB"


def test_physics_pack_database_size_reasonable(physics_pack_path: Path):
    """Verify database file is ~680 MB as documented."""
    db_path = physics_pack_path / "pack.db"
    size_mb = db_path.stat().st_size / (1024 * 1024)

    # Database should be ~680 MB (allow 20% variance)
    expected_mb = 680
    tolerance = 0.20
    min_mb = expected_mb * (1 - tolerance)
    max_mb = expected_mb * (1 + tolerance)

    assert (
        min_mb <= size_mb <= max_mb
    ), f"Database size {size_mb:.0f} MB outside expected range [{min_mb:.0f}, {max_mb:.0f}] MB"


# ============================================================================
# Tarball Creation and Extraction
# ============================================================================


def test_create_physics_pack_tarball(physics_pack_path: Path, tmp_path: Path):
    """Test creating tarball from physics pack."""
    from wikigr.packs.distribution import create_pack_archive

    output_path = tmp_path / "physics-expert.tar.gz"
    create_pack_archive(physics_pack_path, output_path)

    # Verify tarball created
    assert output_path.exists()
    assert output_path.suffix == ".gz"

    # Verify it's a valid tarball
    assert tarfile.is_tarfile(output_path)


def test_physics_pack_tarball_size(physics_pack_path: Path, tmp_path: Path):
    """Test compressed tarball is ~340 MB as documented."""
    from wikigr.packs.distribution import create_pack_archive

    output_path = tmp_path / "physics-expert.tar.gz"
    create_pack_archive(physics_pack_path, output_path)

    size_mb = output_path.stat().st_size / (1024 * 1024)

    # Compressed should be ~340 MB (allow 20% variance)
    expected_mb = 340
    tolerance = 0.20
    min_mb = expected_mb * (1 - tolerance)
    max_mb = expected_mb * (1 + tolerance)

    assert (
        min_mb <= size_mb <= max_mb
    ), f"Compressed size {size_mb:.0f} MB outside expected range [{min_mb:.0f}, {max_mb:.0f}] MB"


def test_extract_physics_pack_tarball(physics_pack_path: Path, tmp_path: Path):
    """Test extracting physics pack from tarball."""
    from wikigr.packs.distribution import create_pack_archive, extract_pack_archive

    # Create tarball
    tarball_path = tmp_path / "physics-expert.tar.gz"
    create_pack_archive(physics_pack_path, tarball_path)

    # Extract to new location
    extract_path = tmp_path / "extracted"
    extract_pack_archive(tarball_path, extract_path)

    # Verify extraction
    assert extract_path.exists()
    assert (extract_path / "manifest.json").exists()
    assert (extract_path / "pack.db").exists()


def test_extracted_pack_identical_to_original(physics_pack_path: Path, tmp_path: Path):
    """Test extracted pack has same structure as original."""
    from wikigr.packs.distribution import create_pack_archive, extract_pack_archive

    # Create and extract
    tarball_path = tmp_path / "physics-expert.tar.gz"
    create_pack_archive(physics_pack_path, tarball_path)

    extract_path = tmp_path / "extracted"
    extract_pack_archive(tarball_path, extract_path)

    # Compare manifests
    with open(physics_pack_path / "manifest.json") as f:
        original_manifest = json.load(f)

    with open(extract_path / "manifest.json") as f:
        extracted_manifest = json.load(f)

    assert original_manifest["name"] == extracted_manifest["name"]
    assert original_manifest["version"] == extracted_manifest["version"]


# ============================================================================
# Pack Structure Validation
# ============================================================================


def test_physics_pack_has_required_files(physics_pack_path: Path):
    """Verify pack has all required files."""
    required_files = [
        "manifest.json",
        "pack.db",
        "README.md",
        "ATTRIBUTIONS.txt",
    ]

    for file in required_files:
        file_path = physics_pack_path / file
        assert file_path.exists(), f"Required file missing: {file}"


def test_physics_pack_has_evaluation_directory(physics_pack_path: Path):
    """Verify pack has eval/ directory with questions."""
    eval_dir = physics_pack_path / "eval"
    assert eval_dir.exists(), "eval/ directory missing"
    assert eval_dir.is_dir()

    # Check for questions file
    questions_file = eval_dir / "questions.jsonl"
    assert questions_file.exists(), "eval/questions.jsonl missing"


def test_physics_pack_has_skill_file(physics_pack_path: Path):
    """Verify pack has skill.md for Claude Code integration."""
    skill_file = physics_pack_path / "skill.md"
    assert skill_file.exists(), "skill.md missing"

    # Verify it's not empty
    content = skill_file.read_text()
    assert len(content) > 0


# ============================================================================
# Domain Coverage Validation
# ============================================================================


def test_physics_pack_covers_all_four_domains(physics_pack_path: Path):
    """Verify pack articles cover all 4 physics domains."""
    import kuzu

    db_path = physics_pack_path / "pack.db"
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    # Get all article titles
    result = conn.execute("MATCH (a:Article) RETURN a.title as title")
    titles = result.get_as_df()["title"].tolist()

    # Check domain coverage
    domain_keywords = {
        "classical_mechanics": ["mechanics", "newton", "force", "motion", "momentum"],
        "quantum_mechanics": ["quantum", "wave", "particle", "heisenberg", "schrödinger"],
        "thermodynamics": ["thermodynamic", "entropy", "temperature", "heat", "carnot"],
        "relativity": ["relativity", "einstein", "spacetime", "lorentz"],
    }

    domain_coverage = {domain: False for domain in domain_keywords}

    for domain, keywords in domain_keywords.items():
        for title in titles:
            title_lower = title.lower()
            if any(kw in title_lower for kw in keywords):
                domain_coverage[domain] = True
                break

    # All domains should have coverage
    for domain, covered in domain_coverage.items():
        assert covered, f"Domain '{domain}' not represented in pack articles"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def physics_pack_path() -> Path:
    """Path to physics-expert pack (either installed or built)."""
    # Check if pack exists in standard location
    installed_path = Path.home() / ".wikigr" / "packs" / "physics-expert"
    if installed_path.exists():
        return installed_path

    # Check if pack exists in data directory
    data_path = Path("data/packs/physics-expert")
    if data_path.exists():
        return data_path

    # If neither exists, skip these tests
    pytest.skip("physics-expert pack not found (not built yet)")
