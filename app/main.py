import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.repository_api import router as repository_router
from app.config import settings
from app.services.cleanup_runner import cleanup_loop, run_sweep

logger = logging.getLogger(__name__)

# Nothing configures the root logger, so without this every `logger.info` in the
# cleanup path is silently discarded. That matters more than usual here: the
# sweeper deletes user data with no UI trace, so the log line is the only record
# that a repository was reclaimed. Uvicorn configures its own loggers, and this
# only adds a handler to the root it did not set one on.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
# Third-party libraries are extremely chatty at INFO; keep the app's own logs.
for noisy in ("httpx", "httpcore", "urllib3", "sentence_transformers"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reclaim anything that expired while the process was down, then keep
    # sweeping in the background. Cancelled cleanly on shutdown.
    try:
        await asyncio.to_thread(run_sweep)
    except Exception:
        logger.exception("startup cleanup sweep failed")

    stop = asyncio.Event()
    task = asyncio.create_task(cleanup_loop(stop))
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

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
