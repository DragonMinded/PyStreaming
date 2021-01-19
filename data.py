import os
from typing import Any, Dict, Optional

import alembic.config  # type: ignore
from alembic.migration import MigrationContext  # type: ignore
from alembic.autogenerate import compare_metadata  # type: ignore
from sqlalchemy import Table, Column, MetaData, create_engine  # type: ignore
from sqlalchemy.orm import scoped_session, sessionmaker  # type: ignore
from sqlalchemy.engine import Engine  # type: ignore
from sqlalchemy.engine.result import ResultProxy  # type: ignore
from sqlalchemy.sql import text  # type: ignore
from sqlalchemy.exc import ProgrammingError  # type: ignore
from sqlalchemy.types import String, Integer  # type: ignore


metadata = MetaData()


"""
Table for storing streamer settings.
"""
streamersettings = Table(  # type: ignore
    'streamersettings',
    metadata,
    Column('username', String(256), nullable=False, unique=True),
    Column('key', String(256), nullable=False, unique=True),
)


class DBCreateException(Exception):
    pass


class Data:
    """
    An object that is meant to be used as a singleton, in order to hold
    DB configuration info and provide a set of functions for querying
    and storing data.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initializes the data object.

        Parameters:
            config - A config structure with a 'database' section which is used
                     to initialize an internal DB connection.
        """
        session_factory = sessionmaker(
            bind=config['database']['engine'],
            autoflush=True,
            autocommit=True,
        )
        self.__config = config
        self.__session = scoped_session(session_factory)
        self.__url = Data.sqlalchemy_url(config)

    @classmethod
    def sqlalchemy_url(cls, config: Dict[str, Any]) -> str:
        return f"mysql://{config['database']['user']}:{config['database']['password']}@{config['database']['address']}/{config['database']['database']}?charset=utf8mb4"

    @classmethod
    def create_engine(cls, config: Dict[str, Any]) -> Engine:
        return create_engine(  # type: ignore
            Data.sqlalchemy_url(config),
            pool_recycle=3600,
        )

    def __exists(self) -> bool:
        # See if the DB was already created
        try:
            cursor = self.__session.execute(text('SELECT COUNT(version_num) AS count FROM alembic_version'))
            return (cursor.fetchone()['count'] == 1)
        except ProgrammingError:
            return False

    def __alembic_cmd(self, command: str, *args: str) -> None:
        base_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), './')
        alembicArgs = [
            '-c',
            os.path.join(base_dir, 'alembic.ini'),
            '-x',
            f'script_location={base_dir}',
            '-x',
            f'sqlalchemy.url={self.__url}',
            command,
        ]
        alembicArgs.extend(args)
        os.chdir(base_dir)
        alembic.config.main(argv=alembicArgs)

    def create(self) -> None:
        """
        Create any tables that need to be created.
        """
        if self.__exists():
            # Cowardly refused to do anything, we should be using the upgrade path instead.
            raise DBCreateException('Tables already created, use upgrade to upgrade schema!')

        metadata.create_all(  # type: ignore
            self.__config['database']['engine'].connect(),
            checkfirst=True,
        )

        # Stamp the end revision as if alembic had created it, so it can take off after this.
        self.__alembic_cmd(
            'stamp',
            'head',
        )

    def generate(self, message: str, allow_empty: bool) -> None:
        """
        Generate upgrade scripts using alembic.
        """
        if not self.__exists():
            raise DBCreateException('Tables have not been created yet, use create to create them!')

        # Verify that there are actual changes, and refuse to create empty migration scripts
        context = MigrationContext.configure(self.__config['database']['engine'].connect(), opts={'compare_type': True})
        diff = compare_metadata(context, metadata)
        if (not allow_empty) and (len(diff) == 0):
            raise DBCreateException('There is nothing different between code and the DB, refusing to create migration!')

        self.__alembic_cmd(
            'revision',
            '--autogenerate',
            '-m',
            message,
        )

    def upgrade(self) -> None:
        """
        Upgrade an existing DB to the current model.
        """
        if not self.__exists():
            raise DBCreateException('Tables have not been created yet, use create to create them!')

        self.__alembic_cmd(
            'upgrade',
            'head',
        )

    def close(self) -> None:
        """
        Close any open data connection.
        """
        # Make sure we don't leak connections between web requests
        if self.__session is not None:
            self.__session.close()
            self.__session = None

    def execute(self, sql: str, params: Optional[Dict[str, Any]]=None, safe_write_operation: bool=False) -> ResultProxy:
        """
        Given a SQL string and some parameters, execute the query and return the result.

        Parameters:
            sql - The SQL statement to execute.
            params - Dictionary of parameters which will be substituted into the sql string.

        Returns:
            A SQLAlchemy ResultProxy object.
        """
        if self.__config['database'].get('read_only', False):
            # See if this is an insert/update/delete
            for write_statement in [
                "insert into ",
                "update ",
                "delete from ",
            ]:
                if write_statement in sql.lower() and not safe_write_operation:
                    raise Exception('Read-only mode is active!')
        return self.__session.execute(  # type: ignore
            text(sql),
            params if params is not None else {},
        )
