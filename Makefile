# Engagement & Personalization Engine - Makefile
# ==============================================
# Common development and deployment tasks

.PHONY: help install dev test lint format clean docker-up docker-down

# Colors for output
BLUE=\033[0;34m
GREEN=\033[0;32m
YELLOW=\033[0;33m
NC=\033[0m # No Color

help:
	@echo "$(BLUE)Engagement & Personalization Engine - Available Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup:$(NC)"
	@echo "  make install          Install Python dependencies"
	@echo "  make dev              Install dev dependencies"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make lint             Run code quality checks"
	@echo "  make format           Auto-format code"
	@echo "  make test             Run test suite"
	@echo "  make test-cov         Run tests with coverage report"
	@echo ""
	@echo "$(YELLOW)Docker:$(NC)"
	@echo "  make docker-up        Start Docker services (Redis, Postgres)"
	@echo "  make docker-down      Stop Docker services"
	@echo "  make docker-logs      View Docker logs"
	@echo ""
	@echo "$(YELLOW)Demos:$(NC)"
	@echo "  make demo-engagement  Run engagement model training notebook"
	@echo "  make demo-experiment  Run experiment simulation"
	@echo ""
	@echo "$(YELLOW)Deployment:$(NC)"
	@echo "  make build-image      Build Docker image for segment receiver"
	@echo "  make serve            Start segment receiver (FastAPI)"
	@echo ""

install:
	@echo "$(BLUE)Installing dependencies...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)✓ Installation complete$(NC)"

dev:
	@echo "$(BLUE)Installing dev dependencies...$(NC)"
	pip install -r requirements.txt pytest pytest-cov black flake8 mypy
	@echo "$(GREEN)✓ Dev setup complete$(NC)"

lint:
	@echo "$(BLUE)Running code quality checks...$(NC)"
	black --check .
	flake8 src/ pipelines/ --max-line-length=100
	mypy src/ --ignore-missing-imports
	@echo "$(GREEN)✓ Linting complete$(NC)"

format:
	@echo "$(BLUE)Auto-formatting code...$(NC)"
	black .
	isort .
	@echo "$(GREEN)✓ Formatting complete$(NC)"

test:
	@echo "$(BLUE)Running tests...$(NC)"
	pytest tests/ -v
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-cov:
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	pytest tests/ -v --cov=src --cov=pipelines --cov-report=html
	@echo "$(GREEN)✓ Coverage report: htmlcov/index.html$(NC)"

clean:
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	rm -f .coverage
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

docker-up:
	@echo "$(BLUE)Starting Docker services...$(NC)"
	docker-compose up -d
	@sleep 3
	@echo "$(GREEN)✓ Services running:$(NC)"
	@echo "  - PostgreSQL: localhost:5432 (user: engagement, password: password)"
	@echo "  - Redis: localhost:6379"
	@echo "  - Kafka: localhost:9092"

docker-down:
	@echo "$(BLUE)Stopping Docker services...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

docker-logs:
	docker-compose logs -f

demo-engagement:
	@echo "$(BLUE)Running engagement model training notebook...$(NC)"
	python notebooks/engagement_model_training.py

demo-experiment:
	@echo "$(BLUE)Running experiment simulation...$(NC)"
	python demo/experiment_simulation.py

build-image:
	@echo "$(BLUE)Building Docker image for segment receiver...$(NC)"
	docker build -f pipelines/Dockerfile -t engagement-segment-receiver:latest .
	@echo "$(GREEN)✓ Image built: engagement-segment-receiver:latest$(NC)"

serve:
	@echo "$(BLUE)Starting Segment receiver (FastAPI)...$(NC)"
	uvicorn pipelines.segment_receiver:app --host 0.0.0.0 --port 8000 --reload

serve-prod:
	@echo "$(BLUE)Starting Segment receiver (production)...$(NC)"
	uvicorn pipelines.segment_receiver:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info

.PHONY: feast-apply feast-materialize feast-ui

feast-apply:
	@echo "$(BLUE)Deploying feature definitions to Feast registry...$(NC)"
	feast apply
	@echo "$(GREEN)✓ Features deployed$(NC)"

feast-materialize:
	@echo "$(BLUE)Syncing features offline → online store...$(NC)"
	feast materialize
	@echo "$(GREEN)✓ Features materialized$(NC)"

feast-ui:
	@echo "$(BLUE)Starting Feast UI...$(NC)"
	feast ui
	@echo "$(GREEN)✓ UI running on http://localhost:8501$(NC)"

# Quick start sequence
quick-start: install docker-up
	@echo ""
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Run demos:"
	@echo "     - make demo-engagement"
	@echo "     - make demo-experiment"
	@echo ""
	@echo "  2. Start API server:"
	@echo "     - make serve"
	@echo ""
	@echo "  3. View dashboard:"
	@echo "     - Open dashboard/dashboard.jsx in your React app"
	@echo ""
