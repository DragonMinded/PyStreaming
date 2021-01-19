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


def main() -> None:
    parser = argparse.ArgumentParser(description="A utility for initializing and updating the streaming backend DB.")
    parser.add_argument(
        "operation",
        help="Operation to perform, options include 'create', 'generate', 'upgrade'.",
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
        else:
            raise Exception(f"Unknown operation '{args.operation}'")
    except DBCreateException as e:
        print(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
