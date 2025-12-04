from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

# Create the engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True, # Logs SQL queries to console (great for debugging)
    pool_size=20,
    max_overflow=10
)

# Create the session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependency to be used in endpoints
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session