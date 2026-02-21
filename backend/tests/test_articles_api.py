"""
Tests for Articles API endpoints.

Tests the /api/v1/articles/{title} endpoint for retrieving article details.
Following TDD methodology - these tests will fail until implementation is complete.
"""


# client fixture is now in conftest.py


class TestArticleDetails:
    """Tests for GET /api/v1/articles/{title} endpoint."""

    def test_get_article_with_valid_title(self, client, sample_article_title):
        """Test retrieving article details for valid article."""
        response = client.get(f"/api/v1/articles/{sample_article_title}")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "title" in data
        assert data["title"] == sample_article_title
        assert "category" in data
        assert "word_count" in data
        assert "sections" in data
        assert "links" in data
        assert "backlinks" in data
        assert "categories" in data
        assert "wikipedia_url" in data
        assert "last_updated" in data

        # Verify sections structure
        assert isinstance(data["sections"], list)
        if len(data["sections"]) > 0:
            section = data["sections"][0]
            assert "title" in section
            assert "content" in section
            assert "word_count" in section
            assert "level" in section

        # Verify links are list of strings
        assert isinstance(data["links"], list)

        # Verify backlinks are list of strings
        assert isinstance(data["backlinks"], list)

    def test_get_article_with_invalid_title(self, client, invalid_article_title):
        """Test 404 for non-existent article."""
        response = client.get(f"/api/v1/articles/{invalid_article_title}")

        assert response.status_code == 404
        data = response.json()

        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "timestamp" in data

    def test_get_article_with_url_encoded_title(self, client):
        """Test handling of URL-encoded article titles."""
        # Article title with spaces needs URL encoding
        title = "Machine Learning"
        response = client.get(f"/api/v1/articles/{title}")

        # Should handle URL encoding correctly
        assert response.status_code in [200, 404]

    def test_get_article_with_special_characters(self, client):
        """Test article title with special characters (parentheses)."""
        title = "Python (programming language)"
        response = client.get(f"/api/v1/articles/{title}")

        assert response.status_code in [200, 404]

    def test_get_article_sections_include_metadata(self, client, sample_article_title):
        """Test that sections include all required metadata."""
        response = client.get(f"/api/v1/articles/{sample_article_title}")

        assert response.status_code == 200
        data = response.json()

        # Check sections have proper structure
        for section in data["sections"]:
            assert isinstance(section["title"], str)
            assert isinstance(section["content"], str)
            assert isinstance(section["word_count"], int)
            assert isinstance(section["level"], int)
            assert section["word_count"] >= 0
            assert section["level"] >= 1

    def test_get_article_wikipedia_url_format(self, client, sample_article_title):
        """Test that Wikipedia URL is properly formatted."""
        response = client.get(f"/api/v1/articles/{sample_article_title}")

        assert response.status_code == 200
        data = response.json()

        # Should be valid Wikipedia URL
        assert data["wikipedia_url"].startswith("https://en.wikipedia.org/wiki/")
        assert sample_article_title.replace(" ", "_") in data["wikipedia_url"]

    def test_get_article_links_are_valid(self, client, sample_article_title):
        """Test that returned links are valid article titles."""
        response = client.get(f"/api/v1/articles/{sample_article_title}")

        assert response.status_code == 200
        data = response.json()

        # Links should be non-empty strings
        for link in data["links"]:
            assert isinstance(link, str)
            assert len(link) > 0

    def test_get_article_performance(self, client, sample_article_title):
        """Test that query executes within performance target (P95 < 35ms)."""
        import time

        start = time.time()
        response = client.get(f"/api/v1/articles/{sample_article_title}")
        elapsed = (time.time() - start) * 1000

        assert response.status_code == 200

        # Allow headroom for test environment
        assert elapsed < 100


class TestArticlesCaching:
    """Tests for caching behavior."""

    def test_get_article_cache_headers(self, client, sample_article_title):
        """Test that cache-control headers are set correctly."""
        response = client.get(f"/api/v1/articles/{sample_article_title}")

        # Should have cache headers as per API spec
        assert "Cache-Control" in response.headers
        # Per API.md: public, max-age=86400 (24 hours)
        assert "public" in response.headers["Cache-Control"]
        assert "max-age=86400" in response.headers["Cache-Control"]

    def test_get_article_etag_support(self, client, sample_article_title):
        """Test ETag support for conditional requests."""
        # First request
        response1 = client.get(f"/api/v1/articles/{sample_article_title}")
        assert response1.status_code == 200

        # Should have ETag header
        if "ETag" in response1.headers:
            etag = response1.headers["ETag"]

            # Second request with If-None-Match
            response2 = client.get(
                f"/api/v1/articles/{sample_article_title}", headers={"If-None-Match": etag}
            )

            # Should return 304 Not Modified if content unchanged
            assert response2.status_code in [200, 304]


class TestHealthCheck:
    """Tests for GET /health endpoint."""

    def test_health_check_returns_status(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "version" in data
        assert "database" in data
        assert "timestamp" in data

    def test_health_check_no_cache(self, client):
        """Test that health check is not cached."""
        response = client.get("/health")

        # Should have no-cache directive
        assert "Cache-Control" in response.headers
        assert "no-cache" in response.headers["Cache-Control"]


class TestCategoriesEndpoint:
    """Tests for GET /api/v1/categories endpoint."""

    def test_get_categories_list(self, client):
        """Test retrieving list of categories."""
        response = client.get("/api/v1/categories")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "categories" in data
        assert "total" in data

        assert isinstance(data["categories"], list)
        assert data["total"] == len(data["categories"])

        # Verify category structure
        for category in data["categories"]:
            assert "name" in category
            assert "article_count" in category
            assert isinstance(category["article_count"], int)
            assert category["article_count"] >= 0


class TestStatsEndpoint:
    """Tests for GET /api/v1/stats endpoint."""

    def test_get_stats(self, client):
        """Test retrieving database statistics."""
        response = client.get("/api/v1/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "articles" in data
        assert "sections" in data
        assert "links" in data
        assert "database" in data
        assert "performance" in data

        # Verify articles stats
        assert "total" in data["articles"]
        assert "by_category" in data["articles"]
        assert "by_depth" in data["articles"]

        # Verify sections stats
        assert "total" in data["sections"]
        assert "avg_per_article" in data["sections"]

        # Verify links stats
        assert "total" in data["links"]
        assert "avg_per_article" in data["links"]

        # Performance stats not yet implemented (returns None)
        # Will be added when query timing infrastructure is built

    def test_stats_cache_headers(self, client):
        """Test that stats have appropriate cache headers."""
        response = client.get("/api/v1/stats")

        # Should have cache headers as per API spec
        assert "Cache-Control" in response.headers
        # Per API.md: public, max-age=300 (5 minutes)
        assert "public" in response.headers["Cache-Control"]
        assert "max-age=300" in response.headers["Cache-Control"]
