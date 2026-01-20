"""
Client API for SkypyDB.
"""

import threading
from typing import Optional

from ..db.database import Database
from ..errors import TableAlreadyExistsError, TableNotFoundError
from ..table.table import Table


class Client:
    """
    Main client for interacting with SkypyDB.
    """

    def __init__(self, path: str, dashboard_port: int = 3000, auto_start_dashboard: bool = True):
        """
        Initialize SkypyDB client.
        
        Args:
            path: Path to SQLite database file
            dashboard_port: Port for the dashboard (default: 3000)
            auto_start_dashboard: Whether to automatically start dashboard
        """

        self.path = path
        self.dashboard_port = dashboard_port
        self.db = Database(path)
        self._dashboard_thread: Optional[threading.Thread] = None
        
        if auto_start_dashboard:
            self.start_dashboard()
    
    def create_table(self, table_name: str) -> Table:
        """
        Create a new table.
        
        Args:
            table_name: Name of the table to create
            
        Returns:
            Table instance
            
        Raises:
            TableAlreadyExistsError: If table already exists
        """

        if not self.db.create_table(table_name):
            raise TableAlreadyExistsError(f"Table '{table_name}' already exists")
        return Table(self.db, table_name)
    
    def get_table(self, table_name: str) -> Table:
        """
        Get an existing table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table instance
            
        Raises:
            TableNotFoundError: If table doesn't exist
        """

        if not self.db.table_exists(table_name):
            raise TableNotFoundError(f"Table '{table_name}' not found")
        return Table(self.db, table_name)
    
    def delete_table(self, table_name: str) -> None:
        """
        Delete a table.
        
        Args:
            table_name: Name of the table to delete
            
        Raises:
            TableNotFoundError: If table doesn't exist
        """

        if not self.db.delete_table(table_name):
            raise TableNotFoundError(f"Table '{table_name}' not found so it can't be deleted")
    
    def start_dashboard(self) -> None:
        """
        Start the dashboard in a separate thread.
        """
        
        if self._dashboard_thread and self._dashboard_thread.is_alive():
            return  # Dashboard already running
        
        def run_dashboard():
            import os
            
            # Set environment variables before importing app
            os.environ['SKYPYDB_PATH'] = self.path
            os.environ['SKYPYDB_PORT'] = str(self.dashboard_port)
            
            # Import and run the app
            from ..dashboard.dashboard.dashboard import app
            
            # Use reflex's run method
            try:
                app.run(port=self.dashboard_port, host="127.0.0.1")
                
            except Exception as e:
                print(f"Error starting dashboard: {e}")

                # Fallback to uvicorn if reflex.run doesn't work
                import uvicorn

                uvicorn.run(app, host="127.0.0.1", port=self.dashboard_port, log_level="warning")
        
        self._dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
        self._dashboard_thread.start()
        
        # Give the dashboard a moment to start
        import time
        time.sleep(0.5)
    
    def stop_dashboard(self) -> None:
        """
        Stop the dashboard.
        """

        # Dashboard runs as daemon thread, will stop when main process exits
        pass
    
    def close(self) -> None:
        """
        Close database connection.
        """

        self.db.close()