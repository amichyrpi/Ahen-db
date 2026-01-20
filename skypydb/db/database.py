"""
Database backend using SQLite.
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..errors import TableAlreadyExistsError, TableNotFoundError


class Database:
    """
    Manages SQLite database connections and operations.
    """

    def __init__(self, path: str):
        """
        Initialize database connection.
        
        Args:
            path: Path to SQLite database file
        """

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access
        
    def create_table(self, table_name: str) -> None:
        """
        Create a new table with id and created_at columns.
        
        Args:
            table_name: Name of the table to create
            
        Raises:
            TableAlreadyExistsError: If table already exists
        """

        # Check if table exists
        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        if cursor.fetchone():
            raise TableAlreadyExistsError(f"Table '{table_name}' already exists")
        
        # Create table with id and created_at columns
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()
        
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.
        """

        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None
        
    def delete_table(self, table_name: str) -> None:
        """
        Delete a table.
        
        Args:
            table_name: Name of the table to delete
            
        Raises:
            TableNotFoundError: If table doesn't exist
        """

        if not self.table_exists(table_name):
            raise TableNotFoundError(f"Table '{table_name}' not found")
        
        cursor = self.conn.cursor()

        cursor.execute(f"DROP TABLE {table_name}")
        self.conn.commit()
        
    def get_table_columns(self, table_name: str) -> List[str]:
        """
        Get list of column names for a table.
        """

        if not self.table_exists(table_name):
            raise TableNotFoundError(f"Table '{table_name}' not found")
        
        cursor = self.conn.cursor()

        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]
        
    def add_columns_if_needed(self, table_name: str, columns: List[str]) -> None:
        """
        Add columns to a table if they don't exist.
        
        Args:
            table_name: Name of the table
            columns: List of column names to add
        """

        existing_columns = set(self.get_table_columns(table_name))
        cursor = self.conn.cursor()
        
        for column in columns:
            if column not in existing_columns and column not in ('id', 'created_at'):
                cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column} TEXT"
                )
        
        self.conn.commit()
        
    def insert_data(
        self,
        table_name: str,
        data: Dict[str, Any],
        generate_id: bool = True
    ) -> str:
        """
        Insert data into a table.
        
        Args:
            table_name: Name of the table
            data: Dictionary of column names and values
            generate_id: Whether to generate UUID automatically
            
        Returns:
            The ID of the inserted row
        """

        if not self.table_exists(table_name):
            raise TableNotFoundError(f"Table '{table_name}' not found")
        
        # Generate ID if needed
        if generate_id:
            data['id'] = str(uuid.uuid4())
        
        # Add created_at timestamp
        if 'created_at' not in data:
            data['created_at'] = datetime.now().isoformat()
        
        # Ensure columns exist
        columns_to_add = [col for col in data.keys() if col not in ('id', 'created_at')]
        if columns_to_add:
            self.add_columns_if_needed(table_name, columns_to_add)
        
        # Build INSERT query
        columns = list(data.keys())
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        
        cursor = self.conn.cursor()

        cursor.execute(
            f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})",
            [str(data[col]) for col in columns]
        )
        self.conn.commit()
        
        return data['id']
        
    def search(
        self,
        table_name: str,
        index: Optional[str] = None,
        **filters
    ) -> List[Dict[str, Any]]:
        """
        Search for data in a table.
        
        Args:
            table_name: Name of the table
            index: Value to search for in any column (searches all columns if column not specified)
            **filters: Additional filters as keyword arguments (column name = value)
            
        Returns:
            List of dictionaries containing matching rows
        """

        if not self.table_exists(table_name):
            raise TableNotFoundError(f"Table '{table_name}' not found")
        
        conditions = []
        params = []
        
        # Add index condition if provided
        # Index searches across all non-standard columns (OR condition)
        if index is not None:
            columns = self.get_table_columns(table_name)
            non_standard_columns = [col for col in columns if col not in ('id', 'created_at')]
            
            if non_standard_columns:
                # Search index value in any of the non-standard columns
                index_conditions = []
                for col in non_standard_columns:
                    index_conditions.append(f"{col} = ?")
                    params.append(str(index))
                conditions.append(f"({' OR '.join(index_conditions)})")
        
        # Add additional filters (AND conditions)
        for column, value in filters.items():
            if column not in ('id', 'created_at'):
                # Handle list values - use IN clause
                if isinstance(value, list) and len(value) > 0:
                    placeholders = ', '.join(['?' for _ in value])
                    conditions.append(f"{column} IN ({placeholders})")
                    params.extend([str(v) for v in value])
                else:
                    conditions.append(f"{column} = ?")
                    params.append(str(value))
        
        # Build query
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM {table_name} WHERE {where_clause}"
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        
        # Convert rows to dictionaries
        results = []
        for row in cursor.fetchall():
            results.append(dict(row))
        
        return results
        
    def get_all_tables(self) -> List[str]:
        """
        Get list of all table names.
        """

        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        return [row[0] for row in cursor.fetchall()]
        
    def get_all_data(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get all data from a table.
        """

        if not self.table_exists(table_name):
            raise TableNotFoundError(f"Table '{table_name}' not found")
        
        cursor = self.conn.cursor()

        cursor.execute(f"SELECT * FROM {table_name}")
        
        results = []
        for row in cursor.fetchall():
            results.append(dict(row))
        
        return results
        
    def close(self) -> None:
        """
        Close database connection.
        """

        if self.conn:
            self.conn.close()