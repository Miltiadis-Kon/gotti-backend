import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
from config.settings import settings


class ConnectionPool:
    """MySQL connection pool with context manager support."""

    def __init__(self):
        self._pool: pooling.MySQLConnectionPool | None = None

    def initialize(self) -> None:
        """Create the connection pool. Call once at startup."""
        self._pool = pooling.MySQLConnectionPool(
            pool_name='gotti_pool',
            pool_size=10,
            pool_reset_session=True,
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            autocommit=False,
        )

    def close(self) -> None:
        """Close all connections in the pool."""
        # mysql-connector-python pools don't have an explicit close,
        # but we clear the reference for clean shutdown.
        self._pool = None

    @contextmanager
    def get_connection(self):
        """Yield a connection from the pool with auto-commit/rollback."""
        if self._pool is None:
            raise RuntimeError('Connection pool not initialized. Call initialize() first.')
        conn = self._pool.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def get_cursor(self, dictionary: bool = True):
        """Yield a cursor from a pooled connection. Auto-commits on success."""
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=dictionary)
            try:
                yield cursor
            finally:
                cursor.close()


# Singleton pool instance
pool = ConnectionPool()
