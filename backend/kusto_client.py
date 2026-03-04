"""
CxE Care Evaluation Agent - Kusto Client

Handles all interactions with Azure Data Explorer (Kusto) clusters.
Discovers databases, tables, schemas, and retrieves sample data to
inform golden-dataset generation.
"""

from __future__ import annotations

import logging
from typing import Any

from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoServiceError

from .config import settings
from .models import KustoTableInfo

logger = logging.getLogger(__name__)


class KustoDataClient:
    """Client for querying the CxE Data Platform Kusto cluster."""

    def __init__(self, cluster_url: str | None = None, database: str | None = None):
        self.cluster_url = cluster_url or settings.KUSTO_CLUSTER_URL
        self.default_database = database or settings.KUSTO_DATABASE
        self._client: KustoClient | None = None

    # ── Connection ─────────────────────────────────────────────────────

    def _get_client(self) -> KustoClient:
        """Lazily create and cache an authenticated Kusto client."""
        if self._client is None:
            try:
                # Try DefaultAzureCredential first (works with az login / managed identity)
                credential = DefaultAzureCredential()
                kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
                    self.cluster_url, credential
                )
            except Exception:
                # Fallback to interactive browser login
                logger.info("Falling back to interactive browser login for Kusto.")
                credential = InteractiveBrowserCredential()
                kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
                    self.cluster_url, credential
                )
            self._client = KustoClient(kcsb)
        return self._client

    def _execute_query(self, query: str, database: str | None = None) -> list[dict[str, Any]]:
        """Execute a KQL query and return results as a list of dicts."""
        db = database or self.default_database
        client = self._get_client()
        try:
            response = client.execute(db, query)
            rows: list[dict[str, Any]] = []
            for table in response.primary_results:
                columns = [col.column_name for col in table.columns]
                for row in table:
                    rows.append(dict(zip(columns, [row[c] for c in columns])))
            return rows
        except KustoServiceError as exc:
            logger.error("Kusto query error: %s", exc)
            raise

    # ── Discovery ──────────────────────────────────────────────────────

    def list_databases(self) -> list[str]:
        """List databases available on the cluster."""
        rows = self._execute_query(".show databases | project DatabaseName")
        return [r["DatabaseName"] for r in rows]

    def list_tables(self, database: str | None = None) -> list[str]:
        """List tables in a database."""
        rows = self._execute_query(
            ".show tables | project TableName", database=database
        )
        return [r["TableName"] for r in rows]

    def get_table_schema(self, table_name: str, database: str | None = None) -> list[dict[str, str]]:
        """Get column names and types for a table."""
        query = f".show table {table_name} schema | project ColumnName, ColumnType"
        rows = self._execute_query(query, database=database)
        return [{"name": r["ColumnName"], "type": r["ColumnType"]} for r in rows]

    def get_table_info(self, table_name: str, database: str | None = None) -> KustoTableInfo:
        """Get comprehensive information about a table."""
        db = database or self.default_database
        schema = self.get_table_schema(table_name, db)

        # Get row count
        count_rows = self._execute_query(
            f"{table_name} | count", database=db
        )
        row_count = count_rows[0].get("Count", 0) if count_rows else None

        # Get sample data (top 5 rows)
        sample = self._execute_query(
            f"{table_name} | take 5", database=db
        )

        return KustoTableInfo(
            database=db,
            table_name=table_name,
            columns=schema,
            row_count=row_count,
            sample_data=sample,
        )

    # ── Data retrieval for dataset generation ──────────────────────────

    def search_tables_by_keyword(self, keyword: str, database: str | None = None) -> list[str]:
        """Find tables whose names contain a keyword (case-insensitive)."""
        all_tables = self.list_tables(database)
        kw = keyword.lower()
        return [t for t in all_tables if kw in t.lower()]

    def get_case_data_sample(
        self, database: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Retrieve sample case/support data for dataset generation."""
        # Try common case-related table names
        candidate_tables = [
            "SupportCases", "Cases", "CaseData", "Incidents",
            "ServiceRequests", "CaseDetails", "CaseHistory",
        ]
        tables = self.list_tables(database)
        for candidate in candidate_tables:
            if candidate in tables:
                return self._execute_query(
                    f"{candidate} | take {limit}", database=database
                )
        # If no known table, search for anything with "case" or "incident"
        matching = self.search_tables_by_keyword("case", database)
        matching.extend(self.search_tables_by_keyword("incident", database))
        if matching:
            return self._execute_query(
                f"{matching[0]} | take {limit}", database=database
            )
        return []

    def get_sm_data_sample(
        self, database: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Retrieve sample Service Manager (SM) data."""
        candidate_tables = [
            "ServiceManager", "SMData", "SMCases", "SMIncidents",
            "ServiceManagerCases", "SMTickets",
        ]
        tables = self.list_tables(database)
        for candidate in candidate_tables:
            if candidate in tables:
                return self._execute_query(
                    f"{candidate} | take {limit}", database=database
                )
        matching = self.search_tables_by_keyword("sm", database)
        matching.extend(self.search_tables_by_keyword("service", database))
        if matching:
            return self._execute_query(
                f"{matching[0]} | take {limit}", database=database
            )
        return []

    def execute_custom_query(
        self, query: str, database: str | None = None
    ) -> list[dict[str, Any]]:
        """Execute a user-supplied KQL query."""
        return self._execute_query(query, database=database)

    def discover_relevant_tables(
        self, scenario_keywords: list[str], database: str | None = None
    ) -> list[KustoTableInfo]:
        """Discover tables relevant to a scenario based on keywords."""
        relevant: list[KustoTableInfo] = []
        seen: set[str] = set()
        for kw in scenario_keywords:
            for table_name in self.search_tables_by_keyword(kw, database):
                if table_name not in seen:
                    seen.add(table_name)
                    try:
                        info = self.get_table_info(table_name, database)
                        relevant.append(info)
                    except Exception as exc:
                        logger.warning("Could not get info for table %s: %s", table_name, exc)
        return relevant
