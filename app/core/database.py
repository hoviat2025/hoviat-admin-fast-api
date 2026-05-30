from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

# Initialize the asynchronous engine for PostgreSQL/SQLAlchemy
engine = create_async_engine(
    settings.DATABASE_URL,
    # Set to True to log all SQL queries (useful for debugging in development)
    echo=False, 
    # Validates connection health by 'pinging' the database before checking out 
    # a connection from the pool. This prevents 'Server has gone away' errors.
    pool_pre_ping=True, 
    # Number of permanent connections to keep in the pool
    pool_size=20,
    # Maximum number of temporary connections allowed during high-traffic spikes
    max_overflow=10,
    
    # 🔴 ONLY use connect_args. 
    # This correctly tells the asyncpg driver to turn off its cache 
    # so it won't crash when traffic is high or PgBouncer swaps connections.
    connect_args={"statement_cache_size": 0} 
)

# Database session factory for generating new session instances
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # In async contexts, we disable attribute expiration on commit to prevent 
    # secondary, implicit IO calls when accessing objects after a transaction.
    expire_on_commit=False
)

async def get_db():
    """
    Dependency generator that yields a database session.
    
    Ensures that the session is properly closed after the request is finished,
    even if an exception occurs during the process.
    """
    async with AsyncSessionLocal() as session:
        yield session