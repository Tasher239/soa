```bash
docker-compose up --build
```

| url                                  | data                 |
|--------------------------------------|----------------------|
| `http://localhost:8000/docs`         | Swagger UI           |
| `http://localhost:8000/redoc`        | ReDoc                |
| `http://localhost:8000/health`       | Health check         |
| `http://localhost:8000/openapi.json` | OpenAPI схема (JSON) |

генерация Pydantic-моделей из OpenAPI

```bash
datamodel-codegen \
  --input openapi/marketplace.yaml \
  --input-file-type openapi \
  --output generated/models.py \
  --output-model-type pydantic_v2.BaseModel
```

```
hw2_openAPI_CRUD/
├── app/
│   ├── main.py                        # Точка входа FastAPI
│   ├── core/config.py                 # Настройки (env vars)
│   ├── domain/                        # Сущности и интерфейсы репозиториев
│   ├── application/use_cases/         # Бизнес-логика
│   ├── infrastructure/                # БД, ORM, JWT, репозитории
│   └── presentation/                  # Роутеры, middleware, error handlers
├── openapi/marketplace.yaml           # OpenAPI 3.1 спецификация
├── generated/                         # Pydantic-модели (генерируются, в .gitignore)
├── alembic/                           # Alembic миграции
├── scripts/generate_models.sh         # Кодогенерация из OpenAPI
├── Dockerfile
└── docker-compose.yml
```
