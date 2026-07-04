from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import close_driver, get_driver
from .routers import analysis, ask, edges, graph, nodes, review, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_driver()


app = FastAPI(title="IndustryNetworkMap API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    try:
        get_driver().verify_connectivity()
        neo4j_status = "up"
    except Exception:
        neo4j_status = "down"
    return {"status": "ok", "neo4j": neo4j_status}


app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(nodes.router, prefix="/api", tags=["nodes"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(edges.router, prefix="/api", tags=["edges"])
app.include_router(analysis.router, prefix="/api", tags=["analysis"])
app.include_router(review.router, prefix="/api", tags=["review"])
app.include_router(ask.router, prefix="/api", tags=["ask"])
