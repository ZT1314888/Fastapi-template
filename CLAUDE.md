# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Global Development Rules

### Code Style & Formatting

**Naming Conventions**:
- Use underscores for function and variable names (`function_name`, `variable_name`)
- Use hyphens for routes and enum labels (`route-name`, `enum-label`)
- Use modern, non-deprecated syntax when writing code

**Automated Quality Checks** (applied by post-write hooks):
- **Black**: Automatic code formatting (88 char line length, double quotes)
- **isort**: Import sorting (stdlib → third-party → local, alphabetical)
- **Flake8**: Critical error checking (E9, F63, F7, F82 - syntax errors, undefined variables)

### Design Patterns

#### Dependency Injection Pattern (MANDATORY)

**ALL service classes MUST follow the dependency injection pattern. DO NOT use singleton patterns or static methods.**

**✅ Correct Pattern - Dependency Injection:**

```python
# In service file (e.g., app/services/client/example.py)
class ExampleService:
    """Example service with dependency injection"""

    def __init__(self, dependency_service: DependencyService = None):
        """Initialize with dependencies"""
        self.dependency_service = dependency_service or DependencyService()

    async def process_data(self, db: AsyncSession, data: dict):
        """Instance method - uses self"""
        result = await self.dependency_service.validate(data)
        return result

# Dependency injection provider function
def get_example_service() -> ExampleService:
    """Get ExampleService instance (dependency injection)"""
    dependency_service = get_dependency_service()  # Get dependencies
    return ExampleService(dependency_service=dependency_service)
```

**In route handlers:**

```python
# In route file (e.g., app/api/client/v1/example.py)
from app.services.client.example import ExampleService, get_example_service

@router.post("/example")
async def example_handler(
    service: ExampleService = Depends(get_example_service),  # Inject service
    db: AsyncSession = Depends(get_db)
):
    result = await service.process_data(db, data)
    return ApiResponse.success(data=result)
```

**❌ FORBIDDEN Patterns:**

```python
# ❌ DO NOT use singleton instances
example_service = ExampleService()  # FORBIDDEN

# ❌ DO NOT use static methods
class ExampleService:
    @staticmethod
    async def process_data(db: AsyncSession):  # FORBIDDEN
        pass

# ❌ DO NOT use class methods
class ExampleService:
    @classmethod
    async def process_data(cls, db: AsyncSession):  # FORBIDDEN
        pass
```

**Key Requirements:**
- **All methods MUST be instance methods** (use `self` parameter, not `@staticmethod` or `@classmethod`)
- **Each service MUST have a `get_xxx_service()` provider function** for dependency injection
- **Routes MUST inject services using `Depends(get_xxx_service)`**
- **NO module-level singleton instances** (e.g., `service = Service()`)
- **Service dependencies MUST be injected through constructor** (`__init__`)

**Service Dependency Chain Example:**

```python
# Service A depends on Service B
class ServiceA:
    def __init__(self, service_b: ServiceB = None):
        self.service_b = service_b or ServiceB()

def get_service_a() -> ServiceA:
    service_b = get_service_b()  # Get dependency first
    return ServiceA(service_b=service_b)
```

#### General Design Patterns
- Place database model conversion in the service layer to keep the routing layer clean
- Handle transactions in the service layer to align business logic with transaction boundaries

### Language Guidelines
- Use English for all code comments and documentation
- Answer questions in Chinese when requested by the user

## Development Commands

### Docker Development Environment (CRITICAL)

**ALWAYS use Docker for development and API testing. DO NOT start the server manually.**

- **Start development environment**: `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d`
- **Stop development environment**: `docker-compose -f docker-compose.yml -f docker-compose.dev.yml down`
- **View logs**: `docker-compose logs -f api`
- **API Port**: Uses `API_PORT` from `.env` file (check the .env file for the actual port number)
- **API Base URL**: `http://localhost:{API_PORT}` (where `{API_PORT}` is the value from .env)

**Important Notes**:
- All API testing MUST use the local Docker environment
- Do NOT use `python main.py` or other manual methods to start the server
- The Docker setup includes all necessary services (PostgreSQL, Redis, etc.)
- Any changes to code will be reflected automatically due to volume mounting

### Virtual Environment (CRITICAL)
- **ALWAYS activate virtual environment first**: `source venv/bin/activate`
- **Command format**: `source venv/bin/activate && python script.py`
- This applies to ALL Python operations: scripts, tests, migrations, etc.

### Server

- **Start development server**: `source venv/bin/activate && python main.py` (runs on port 8001 with hot reload)
- **Start production server**: Set `ENV=production` in .env, then `source venv/bin/activate && python main.py`

### Database (PostgreSQL)

#### Common Commands

- **Install dependencies first**: `source venv/bin/activate && pip install asyncpg psycopg2-binary`
- **Run migrations**: `source venv/bin/activate && alembic upgrade head`
- **Create new migration**: `source venv/bin/activate && alembic revision --autogenerate -m "migration_name"`
- **Downgrade migration**: `source venv/bin/activate && alembic downgrade -1`

#### Database Field Type Requirements (CRITICAL)

**1. ALWAYS use `TIMESTAMP(timezone=True)` for time fields:**

```python
# ✅ Correct - generates PostgreSQL TIMESTAMPTZ
from sqlalchemy import TIMESTAMP, Column

class Example(BaseModel):
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
```

**Why this matters:**
- `TIMESTAMP(timezone=True)` generates `TIMESTAMPTZ` in PostgreSQL
- `TIMESTAMPTZ` stores UTC time and handles timezone conversions automatically
- Prevents timezone-related bugs in production
- Alembic will generate `TIMESTAMPTZ` automatically from this syntax

**2. NEVER use Enum types - use String instead:**

```python
# ❌ Wrong - DO NOT use Enum
from sqlalchemy import Enum

class User(BaseModel):
    status = Column(Enum('active', 'inactive', 'suspended'))  # FORBIDDEN

# ✅ Correct - use String with validation
from sqlalchemy import String

class User(BaseModel):
    status = Column(String(20), nullable=False)  # Use String type
    # Validation should be done at Pydantic schema level
```

**Why this matters:**
- Database-level Enum types are hard to modify (requires migration to add/remove values)
- String types provide flexibility for future changes
- Validation can be handled at application level (Pydantic schemas)
- Easier to maintain and evolve business logic
- Avoids database migration complexity when enum values change

#### Database Architecture

- **Dual Driver Architecture**:
  - `asyncpg`: High-performance async operations (application code)
  - `psycopg2-binary`: Synchronous operations (Alembic migrations only)
- **Lazy Loading**: Engine and session creation deferred to avoid import issues during migrations
- **Connection Pooling**: Production uses 20 connections, 10 max overflow, 30-minute recycle
- **Separate Scheduler Engine**: 5 connections for background tasks

### Background Tasks

- **Start Celery worker**: `source venv/bin/activate && python celery_worker.py`
- **Start Celery beat (scheduler)**: `source venv/bin/activate && celery -A app.core.celery_app beat --loglevel=info`
- **Monitor Celery**: `source venv/bin/activate && celery -A app.core.celery_app flower`

## Architecture Overview

### API Structure

The API follows a dual-client architecture pattern:

- **Client API** (`/api/v1/`): Public-facing endpoints for client applications
- **Backoffice API** (`/api/v1/backoffice/`): Admin/management endpoints with authentication

### Documentation Access

#### Environment-Controlled Documentation Navigation
- **Development/Preview**: Root path (`/`) provides complete API documentation navigation
- **Production**: Root path hidden to prevent API structure disclosure
- **Direct Access**: All documentation endpoints remain accessible via direct URLs

#### Swagger/OpenAPI Documentation
- **Client Docs**: `/client/docs` (Swagger UI), `/client/redoc` (ReDoc)
- **Backoffice Docs**: `/backoffice/docs` (Swagger UI), `/backoffice/redoc` (ReDoc)
- **JSON Export**: `/api-docs/client.json`, `/api-docs/backoffice.json`
- **Environment Control**: Controlled by `ENV` environment variable (`development`, `preview`, `production`)

### Core Components

#### Application Layer (`app/`)

- **`route/route.py`**: Main FastAPI app factory with middleware, CORS, and global exception handlers
- **`route/router_registry.py`**: Centralized route configuration management to avoid duplication
- **`core/config.py`**: Environment-based configuration using Pydantic Settings (PostgreSQL, Redis, Celery, JWT, AWS S3, Email)
- **`core/celery_app.py`**: Celery configuration for background tasks with Redis broker

#### Configuration Layer

- **`configs/`**: Application configuration definitions separated from core system configs
  - `client_swagger_config.py`: Client API Swagger configuration
  - `backoffice_swagger_config.py`: Backoffice API Swagger configuration
  - `docs_apps.py`: Standalone documentation applications

#### Data Layer

- **`db/`**: SQLAlchemy async setup with session management and transaction contexts
  - `base.py`: PostgreSQL connection setup with lazy engine creation
  - `models.py`: Base declarative model for all database models
  - `session.py`: General transaction management and asynchronous sessions
- **`models/`**: SQLAlchemy ORM models inheriting from BaseModel (includes id, created_at, updated_at)
- **`migrations/`**: Alembic database migrations configured for PostgreSQL

#### Business Logic

- **`services/`**: Business logic separated by client/backoffice domains
- **`schemas/`**: Pydantic models for request/response validation
  - `response.py`: Unified response format using `ApiResponse`
  - `paginator.py`: Pagination utilities
- **`api/`**: Route handlers organized by client/backoffice and versioned (v1)
  - `docs_export.py`: API documentation export functionality

#### Background Processing

- **`schedule/`**: Celery task definitions and job scheduling
- **`schedule/jobs/`**: Individual scheduled task implementations

#### Script Management

- **`scripts/`**: Important production and utility scripts (committed to repository)
  - Deployment scripts, database maintenance, backup utilities
  - Permanent, reusable scripts for operations and development
- **`shell/`**: Temporary development scripts (excluded from git)
  - Quick tests, debugging helpers, one-off analysis scripts
  - Not committed to repository (in `.gitignore`)

### Response Design

#### Unified Response Format

- **ALWAYS use `ApiResponse`** from `app.schemas.response` (NOT `SuccessResponse`)
- For pagination, refer to `paginator.py`

```python
from app.schemas.response import ApiResponse  # ✓ Correct

return ApiResponse.success(data=result)
```

#### Exception Handling

- Use `APIException` from `app.exceptions.http_exceptions.py` for standardized exception responses

#### HTTP Status Code Guidelines

- **400 (Bad Request)**: User-facing errors that should be displayed to users
  - Validation errors, missing required fields, invalid input formats
  - These error messages will be shown directly to users in the frontend
- **404 (Not Found)**: Resource not found errors (NOT displayed to users)
- **500 (Internal Server Error)**: System/server errors (NOT displayed to users)

**Important**: Only 400 status code errors are displayed to end users.

### Service Layer Pattern

```python
# In route handler
@router.post("/example")
async def example_handler(
    service: ExampleService = Depends(get_example_service),  # Dependency injection
    db: AsyncSession = Depends(get_db)
):
    result = await service.process_data(db)  # Business logic in service
    return ApiResponse.success(data=result)

# In service layer
async def process_data(self, db: AsyncSession):
    async with transaction(db):  # Transaction in service layer
        # Business logic here
        pass
```

### Key Dependencies

- **FastAPI**: Web framework with OpenAPI documentation
- **SQLAlchemy**: Async ORM with PostgreSQL backend
- **asyncpg**: High-performance async PostgreSQL driver for application operations
- **psycopg2-binary**: PostgreSQL adapter for Alembic migrations (sync operations)
- **Alembic**: Database migrations
- **Celery**: Background task processing with Redis broker
- **Pydantic**: Data validation and settings management
- **Redis**: Caching and Celery broker
- **JWT**: Authentication using python-jose
- **AWS SDK**: S3 integration via boto3

### Configuration Requirements

Environment variables needed in `.env`:

- Database: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`
- Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- JWT: `SECRET_KEY`
- AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_BUCKET_NAME`
- Email: Mail server or Brevo API credentials

### File Organization Rules

- **Scripts**: `scripts/` for permanent scripts, `shell/` for temporary scripts (gitignored)
- **Documentation**: MUST follow `docs/` subdirectory structure - see `docs/README.md` for details
- **NEVER create files directly in `docs/` root** - always use appropriate subdirectories (api/, architecture/, deployment/, etc.)
- Always check for existing files before creating new ones to avoid duplication

### Logging & Monitoring

- Structured logging with file rotation in `logs/` directory
- Redis-based log aggregation with separate consumer thread
- Master process detection to prevent duplicate background services

## Migration Best Practices

When creating or modifying database migrations:

1. **Always install both drivers first**: `asyncpg` and `psycopg2-binary`
2. **Use `TIMESTAMP(timezone=True)`** for all time fields (see Database Field Type Requirements above)
3. **Test in development first**: Verify migrations work before deploying to production
4. **Backup production database**: Always backup before running migrations in production
5. **Review auto-generated migrations**: Alembic's autogenerate is helpful but not perfect - always review the generated code
