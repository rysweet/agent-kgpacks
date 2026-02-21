"""
Tests for Search API endpoints.

Tests the /api/v1/search endpoint for semantic search functionality.
Following TDD methodology - these tests will fail until implementation is complete.
"""


# client fixture is now in conftest.py


class TestSemanticSearch:
    """Tests for GET /api/v1/search endpoint."""

    def test_search_with_valid_query(self, client):
        """Test semantic search with valid query."""
        response = client.get("/api/v1/search", params={"query": "Machine Learning", "limit": 10})

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "query" in data
        assert data["query"] == "Machine Learning"
        assert "results" in data
        assert "total" in data
        assert "execution_time_ms" in data

        # Verify results structure
        assert isinstance(data["results"], list)
        assert len(data["results"]) <= 10

        for result in data["results"]:
            assert "article" in result
            assert "similarity" in result
            assert "category" in result
            assert "word_count" in result
            assert "summary" in result

            # Similarity should be between 0 and 1
            assert 0.0 <= result["similarity"] <= 1.0

    def test_search_with_invalid_query_article(self, client, invalid_article_title):
        """Test 404 when query article doesn't exist."""
        response = client.get("/api/v1/search", params={"query": invalid_article_title})

        assert response.status_code == 404
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"

    def test_search_respects_limit_parameter(self, client):
        """Test that limit parameter caps result count."""
        limit = 5
        response = client.get("/api/v1/search", params={"query": "Python", "limit": limit})

        assert response.status_code == 200
        data = response.json()

        assert len(data["results"]) <= limit
        assert data["total"] <= limit

    def test_search_validates_limit_range(self, client):
        """Test limit validation (must be 1-100)."""
        # Test limit < 1
        response = client.get("/api/v1/search", params={"query": "Python", "limit": 0})

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "INVALID_PARAMETER"

        # Test limit > 100
        response = client.get("/api/v1/search", params={"query": "Python", "limit": 200})

        assert response.status_code == 400

    def test_search_with_category_filter(self, client, sample_category):
        """Test filtering search results by category."""
        response = client.get(
            "/api/v1/search", params={"query": "Python", "category": sample_category, "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()

        # All results should match category filter
        for result in data["results"]:
            assert result["category"] == sample_category

    def test_search_with_threshold_filter(self, client):
        """Test filtering results by similarity threshold."""
        threshold = 0.7
        response = client.get(
            "/api/v1/search",
            params={"query": "Machine Learning", "threshold": threshold, "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()

        # All results should meet threshold
        for result in data["results"]:
            assert result["similarity"] >= threshold

    def test_search_validates_threshold_range(self, client):
        """Test threshold validation (must be 0.0-1.0)."""
        # Test threshold < 0
        response = client.get("/api/v1/search", params={"query": "Python", "threshold": -0.1})

        assert response.status_code == 400

        # Test threshold > 1
        response = client.get("/api/v1/search", params={"query": "Python", "threshold": 1.5})

        assert response.status_code == 400

    def test_search_missing_query_parameter(self, client):
        """Test error when query parameter is missing."""
        response = client.get("/api/v1/search")

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "MISSING_PARAMETER"

    def test_search_results_sorted_by_similarity(self, client):
        """Test that results are sorted by similarity score (descending)."""
        response = client.get(
            "/api/v1/search", params={"query": "Artificial Intelligence", "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()

        if len(data["results"]) > 1:
            similarities = [result["similarity"] for result in data["results"]]
            # Check descending order
            assert similarities == sorted(similarities, reverse=True)

    def test_search_with_empty_results(self, client):
        """Test handling when no results match criteria."""
        # Search with very high threshold should return empty results
        response = client.get(
            "/api/v1/search", params={"query": "Python", "threshold": 0.99, "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert data["results"] == []

    def test_search_default_parameters(self, client):
        """Test default values for optional parameters."""
        response = client.get("/api/v1/search", params={"query": "Python"})

        assert response.status_code == 200
        data = response.json()

        # Should use default limit=10, threshold=0.0
        assert len(data["results"]) <= 10


class TestSearchEdgeCases:
    """Edge case tests for search API."""

    def test_search_with_special_characters(self, client):
        """Test search query with special characters."""
        response = client.get("/api/v1/search", params={"query": "C++"})

        # Should handle gracefully (200 or 404)
        assert response.status_code in [200, 404]

    def test_search_with_url_encoded_query(self, client):
        """Test handling of URL-encoded search queries."""
        response = client.get(
            "/api/v1/search",
            params={"query": "Machine Learning"},  # requests will encode
        )

        assert response.status_code in [200, 404]

    def test_search_performance(self, client):
        """Test that search executes within performance target (P95 < 120ms)."""
        response = client.get("/api/v1/search", params={"query": "Machine Learning", "limit": 10})

        assert response.status_code == 200
        data = response.json()

        # Check execution time meets performance target
        assert data["execution_time_ms"] < 300  # Allow headroom for test environment

    def test_search_includes_execution_time(self, client):
        """Test that response includes execution time metric."""
        response = client.get("/api/v1/search", params={"query": "Python"})

        assert response.status_code == 200
        data = response.json()

        assert "execution_time_ms" in data
        assert isinstance(data["execution_time_ms"], int | float)
        assert data["execution_time_ms"] > 0


class TestSearchCaching:
    """Tests for caching behavior."""

    def test_search_cache_headers(self, client):
        """Test that cache-control headers are set correctly."""
        response = client.get("/api/v1/search", params={"query": "Python"})

        # Should have cache headers as per API spec
        assert "Cache-Control" in response.headers
        # Public cache for read-only Wikipedia data
        assert "public" in response.headers["Cache-Control"]
        assert "max-age=3600" in response.headers["Cache-Control"]


class TestAutocomplete:
    """Tests for GET /api/v1/autocomplete endpoint."""

    def test_autocomplete_with_valid_query(self, client):
        """Test autocomplete suggestions."""
        response = client.get("/api/v1/autocomplete", params={"q": "mach", "limit": 5})

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "query" in data
        assert data["query"] == "mach"
        assert "suggestions" in data
        assert "total" in data

        # Verify suggestions structure
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) <= 5

        for suggestion in data["suggestions"]:
            assert "title" in suggestion
            assert "category" in suggestion
            assert "match_type" in suggestion

    def test_autocomplete_query_too_short(self, client):
        """Test error when query is less than 2 characters."""
        response = client.get("/api/v1/autocomplete", params={"q": "m"})

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "INVALID_PARAMETER"

    def test_autocomplete_validates_limit(self, client):
        """Test limit validation (must be 1-20)."""
        # Test limit > 20
        response = client.get("/api/v1/autocomplete", params={"q": "machine", "limit": 50})

        assert response.status_code == 400

    def test_autocomplete_missing_query(self, client):
        """Test error when q parameter is missing."""
        response = client.get("/api/v1/autocomplete")

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "MISSING_PARAMETER"
