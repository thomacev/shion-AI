from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.exceptions_handlers import setup_exception_handlers
from prometheus_fastapi_instrumentator import Instrumentator   # ← nuevo
from app.api import auth, assistants, conversations
from app.core.middleware import RequestContextMiddleware


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Shion AI API for different agents",
    debug=settings.DEBUG,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

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

app.include_router(auth.router)
app.include_router(assistants.router)
app.include_router(conversations.router)


@app.get("/")
def root():
    return {"message": "Shion AI is running!"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}