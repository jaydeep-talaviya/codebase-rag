from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.repository_api import router as repository_router
from app.config import settings

app = FastAPI()

# The frontend is served from a different origin (Vite on :5173), so the
# browser blocks every cross-origin call until this is registered.
# allow_credentials stays False, which is what a wildcard origin would require.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


app.include_router(repository_router)
