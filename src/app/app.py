from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.exceptions_handlers import setup_exception_handlers
from prometheus_fastapi_instrumentator import Instrumentator  # ← nuevo
from app.api import auth, assistants, conversations,documents  # Importar el enrutador de documentos
from app.core.middleware import RequestContextMiddleware, UploadBodyLimitMiddleware
from app.core.gemini_client import close_gemini_client
from app.core.redis import close_redis
from app.db.session import check_embedding_schema, engine
from app.core.rate_limit import limiter

@asynccontextmanager
async def lifespan(app):
    await check_embedding_schema()
    try:
        yield
    finally:
        await close_gemini_client()
        await close_redis()
        await engine.dispose()


app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version="1.0.0",
    description="Shion AI API for different agents",
    debug=settings.DEBUG,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)
app.state.limiter = limiter
setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
Instrumentator().instrument(app).expose(app)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(UploadBodyLimitMiddleware)

app.include_router(auth.router)
app.include_router(assistants.router)
app.include_router(conversations.router)
app.include_router(documents.router)  # Agregar el enrutador de documentos


@app.get("/")
def root():
    return {"message": "Shion AI is running!"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
