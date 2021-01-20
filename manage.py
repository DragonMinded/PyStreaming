import argparse
import sys
import yaml  # type: ignore
from typing import Any, Dict, Optional

from data import Data, DBCreateException


def create(config: Dict[str, Any]) -> None:
    data = Data(config)
    data.create()
    data.close()


def generate(config: Dict[str, Any], message: Optional[str], allow_empty: bool) -> None:
    if message is None:
        raise Exception('Please provide a message!')
    data = Data(config)
    data.generate(message, allow_empty)
    data.close()


def upgrade(config: Dict[str, Any]) -> None:
    data = Data(config)
    data.upgrade()
    data.close()


def addstreamer(config: Dict[str, Any], username: Optional[str], key: Optional[str]) -> None:
    if username is None:
        raise Exception('Please provide a username!')
    if key is None:
        raise Exception('Please provide a stream key!')
    data = Data(config)
    data.execute(
        "INSERT INTO streamersettings (`username`, `key`) VALUES (:username, :key)",
        {'username': username, 'key': key},
    )
    data.close()


def dropstreamer(config: Dict[str, Any], username: Optional[str]) -> None:
    if username is None:
        raise Exception('Please provide a username!')
    data = Data(config)
    data.execute(
        "DELETE FROM streamersettings WHERE username = :username LIMIT 1",
        {'username': username},
    )
    data.close()


def liststreamers(config: Dict[str, Any]) -> None:
    data = Data(config)
    cursor = data.execute("SELECT username FROM streamersettings")
    for result in cursor.fetchall():
        print(f"Streamer: {result['username']}")
    data.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="A utility for initializing and updating the streaming backend DB.")
    parser.add_argument(
        "operation",
        help="Operation to perform, options include 'create', 'generate', 'upgrade', 'addstreamer', 'dropstreamer', 'liststreamers'.",
        type=str,
    )
    parser.add_argument(
        "-m",
        "--message",
        help="Message to use for auto-generated migration scripts.",
        type=str,
    )
    parser.add_argument(
        "-e",
        "--allow-empty",
        help="Allow empty migration script to be generated. Useful for data-only migrations.",
        action='store_true',
    )
    parser.add_argument(
        "-u",
        "--username",
        help="Streamer username to use when adding or dropping a streamer.",
        type=str,
    )
    parser.add_argument(
        "-k",
        "--key",
        help="Stream key in OBS or other streaming program when adding a streamer.",
        type=str,
    )
    parser.add_argument("-c", "--config", help="Core configuration. Defaults to config.yaml", type=str, default="config.yaml")
    args = parser.parse_args()

    config = yaml.safe_load(open(args.config))  # type: ignore
    config['database']['engine'] = Data.create_engine(config)
    try:
        if args.operation == "create":
            create(config)
        elif args.operation == "generate":
            generate(config, args.message, args.allow_empty)
        elif args.operation == "upgrade":
            upgrade(config)
        elif args.operation == "addstreamer":
            addstreamer(config, args.username, args.key)
        elif args.operation == "dropstreamer":
            dropstreamer(config, args.username)
        elif args.operation == "liststreamers":
            liststreamers(config)
        else:
            raise Exception(f"Unknown operation '{args.operation}'")
    except DBCreateException as e:
        print(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
