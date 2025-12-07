from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True, 
    # CRITICAL FIX: This "pings" the DB before giving the connection to the request.
    # If the connection is dead, it throws it away and makes a new one.
    pool_pre_ping=True, 
    pool_size=20,
    max_overflow=10
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False # This is correct for Async. Keep it.
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session