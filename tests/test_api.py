"""
Tests for main API endpoints (src/main.py)
Validates health check, dashboard stats, and trigger endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date
import sys
import os

# Add the project root to python path to import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import app
from src.domain.models import SymbolMaster

client = TestClient(app)

class TestHealthCheck:
    def test_root_health_check(self):
        """Root endpoint should return 200 and system status."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data
        assert "celery" in data

class TestDashboardAPI:
    def test_api_health_endpoint(self):
        """API health endpoint should return provider statuses."""
        response = client.get("/api/dashboard/api-health")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert "gateway_online" in data
        assert isinstance(data["sources"], list)
        
    def test_task_status_endpoint_invalid_id(self):
        """Task status endpoint should handle invalid UUID gracefully."""
        response = client.get("/api/task-status/invalid-uuid-1234")
        # FastAPI might return 422 for path validation or Celery might just return PENDING for unknown IDs
        # So we just check it doesn't 500 error
        assert response.status_code in [200, 422, 404]

class TestTriggerEndpoints:
    def test_trigger_bot1_eod(self):
        """Bot 1 EOD trigger should return a task ID."""
        response = client.post("/trigger/bot1/eod")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "message" in data
        assert "Bot 1" in data["message"]

    def test_trigger_bot2_process(self):
        """Bot 2 process trigger should return a task ID."""
        response = client.post("/trigger/bot2/process")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    def test_trigger_bot3_score(self):
        """Bot 3 score trigger should return a task ID."""
        response = client.post("/trigger/bot3/score")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    def test_trigger_bot4_allocate(self):
        """Bot 4 allocate trigger should return a task ID."""
        response = client.post("/trigger/bot4/allocate")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    def test_trigger_bot5_top20(self):
        """Bot 5 top20 trigger should return a task ID."""
        response = client.post("/trigger/bot5/top20")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    def test_trigger_bot6_stress_test(self):
        """Bot 6 stress test trigger should return a task ID."""
        response = client.post("/trigger/bot6/stress_test")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
