"""
Tests for Graph API endpoints.

Tests the /api/v1/graph endpoint for retrieving graph structure around seed articles.
Following TDD methodology - these tests will fail until implementation is complete.
"""


# client fixture is now in conftest.py


class TestGraphNeighbors:
    """Tests for GET /api/v1/graph endpoint."""

    def test_get_graph_with_valid_article(self, client, sample_article_title):
        """Test retrieving graph for valid article."""
        response = client.get(
            "/api/v1/graph", params={"article": sample_article_title, "depth": 2, "limit": 50}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure matches GraphResponse model
        assert "seed" in data
        assert data["seed"] == sample_article_title
        assert "nodes" in data
        assert "edges" in data
        assert "total_nodes" in data
        assert "total_edges" in data
        assert "execution_time_ms" in data

        # Verify nodes structure
        assert isinstance(data["nodes"], list)
        assert len(data["nodes"]) > 0

        for node in data["nodes"]:
            assert "id" in node
            assert "title" in node
            assert "category" in node
            assert "word_count" in node
            assert "depth" in node
            assert "links_count" in node
            assert "summary" in node

        # Verify edges structure
        assert isinstance(data["edges"], list)

        for edge in data["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "type" in edge
            assert "weight" in edge

    def test_get_graph_with_invalid_article(self, client, invalid_article_title):
        """Test 404 for non-existent article."""
        response = client.get("/api/v1/graph", params={"article": invalid_article_title})

        assert response.status_code == 404
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "timestamp" in data

    def test_get_graph_respects_depth_parameter(self, client, sample_article_title):
        """Test that depth parameter limits graph traversal."""
        # Request depth=1
        response = client.get("/api/v1/graph", params={"article": sample_article_title, "depth": 1})

        assert response.status_code == 200
        data = response.json()

        # All nodes should have depth <= 1
        for node in data["nodes"]:
            assert node["depth"] <= 1

    def test_get_graph_respects_limit_parameter(self, client, sample_article_title):
        """Test that limit parameter caps node count."""
        limit = 10
        response = client.get(
            "/api/v1/graph", params={"article": sample_article_title, "depth": 2, "limit": limit}
        )

        assert response.status_code == 200
        data = response.json()

        # Should not exceed limit
        assert len(data["nodes"]) <= limit

    def test_get_graph_validates_depth_range(self, client, sample_article_title):
        """Test depth validation (must be 1-3)."""
        # Test depth < 1
        response = client.get("/api/v1/graph", params={"article": sample_article_title, "depth": 0})

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "INVALID_PARAMETER"

        # Test depth > 3
        response = client.get("/api/v1/graph", params={"article": sample_article_title, "depth": 5})

        assert response.status_code == 400

    def test_get_graph_validates_limit_range(self, client, sample_article_title):
        """Test limit validation (must be 1-200)."""
        # Test limit < 1
        response = client.get("/api/v1/graph", params={"article": sample_article_title, "limit": 0})

        assert response.status_code == 400

        # Test limit > 200
        response = client.get(
            "/api/v1/graph", params={"article": sample_article_title, "limit": 500}
        )

        assert response.status_code == 400

    def test_get_graph_missing_article_parameter(self, client):
        """Test error when article parameter is missing."""
        response = client.get("/api/v1/graph")

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "MISSING_PARAMETER"

    def test_get_graph_with_category_filter(self, client, sample_article_title, sample_category):
        """Test filtering nodes by category."""
        response = client.get(
            "/api/v1/graph", params={"article": sample_article_title, "category": sample_category}
        )

        assert response.status_code == 200
        data = response.json()

        # All returned nodes should match category
        for node in data["nodes"]:
            if node["category"] is not None:
                assert node["category"] == sample_category

    def test_get_graph_with_isolated_article(self, client):
        """Test article with no outgoing links."""
        # This is an edge case - article exists but has no links
        # Implementation should handle gracefully
        response = client.get("/api/v1/graph", params={"article": "Isolated Article Test"})

        # Should either return 200 with single node or 404
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Should return at least the seed node
            assert len(data["nodes"]) >= 1
            assert data["nodes"][0]["title"] == "Isolated Article Test"

    def test_get_graph_default_parameters(self, client, sample_article_title):
        """Test default values for depth and limit."""
        response = client.get("/api/v1/graph", params={"article": sample_article_title})

        assert response.status_code == 200
        data = response.json()

        # Should use default depth=2, limit=50
        assert len(data["nodes"]) <= 50

        # Should have nodes at depth 0, 1, and possibly 2
        depths = {node["depth"] for node in data["nodes"]}
        assert 0 in depths


class TestGraphEdgeCases:
    """Edge case tests for graph API."""

    def test_get_graph_with_url_encoded_title(self, client):
        """Test handling of URL-encoded article titles."""
        # Article title with spaces should be URL encoded
        response = client.get(
            "/api/v1/graph",
            params={"article": "Machine Learning"},  # requests will encode
        )

        assert response.status_code in [200, 404]

    def test_get_graph_with_special_characters(self, client):
        """Test article titles with special characters."""
        # Test title with parentheses
        response = client.get("/api/v1/graph", params={"article": "Python (programming language)"})

        assert response.status_code in [200, 404]

    def test_get_graph_performance(self, client, sample_article_title):
        """Test that query executes within performance target (P95 < 180ms)."""
        response = client.get(
            "/api/v1/graph", params={"article": sample_article_title, "depth": 2, "limit": 50}
        )

        assert response.status_code == 200
        data = response.json()

        # Check execution time meets performance target
        assert data["execution_time_ms"] < 500  # Allow headroom for test environment

    def test_get_graph_includes_execution_time(self, client, sample_article_title):
        """Test that response includes execution time metric."""
        response = client.get("/api/v1/graph", params={"article": sample_article_title})

        assert response.status_code == 200
        data = response.json()

        assert "execution_time_ms" in data
        assert isinstance(data["execution_time_ms"], int | float)
        assert data["execution_time_ms"] > 0


class TestGraphCaching:
    """Tests for caching behavior."""

    def test_get_graph_cache_headers(self, client, sample_article_title):
        """Test that cache-control headers are set correctly."""
        response = client.get("/api/v1/graph", params={"article": sample_article_title})

        # Should have cache headers as per API spec
        assert "Cache-Control" in response.headers
        # Public cache for read-only Wikipedia data
        assert "public" in response.headers["Cache-Control"]
        assert "max-age=3600" in response.headers["Cache-Control"]
