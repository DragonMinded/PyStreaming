import argparse
import sys
import yaml
from typing import Any, Dict, Optional

from data import Data, DBCreateException


def create(config: Dict[str, Any]) -> None:
    """
    Given a config pointing at a valid MySQL DB, initializes that DB by creating all required tables.
    """

    data = Data(config)
    data.create()
    data.close()


def generate(config: Dict[str, Any], message: Optional[str], allow_empty: bool) -> None:
    """
    Given some changes to the table definitions in the SQL files of this repo, and a config pointing
    at a valid MySQL DB that has previously been initialized and then upgraded to the base revision
    of the repo before modification, generates a migration that will allow a production instance to
    auto-upgrade their DB to mirror your changes.
    """

    if message is None:
        raise Exception('Please provide a message!')
    data = Data(config)
    data.generate(message, allow_empty)
    data.close()


def upgrade(config: Dict[str, Any]) -> None:
    """
    Given a config pointing at a valid MySQL DB that's been created already, runs any pending migrations
    that were checked in since you last ran create or migrate.
    """

    data = Data(config)
    data.upgrade()
    data.close()


def addstreamer(config: Dict[str, Any], username: Optional[str], key: Optional[str]) -> None:
    """
    Given a valid config pointing at a working DB, a username and a key, add a streamer to the network
    identified by that username who will use that key to authenticate on their stream page and as their
    stream key when sending stream data to the RTMP endpoint.
    """

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
    """
    Given a valid config pointing at a working DB and a username of an existing user, drop that streamer
    from the network.
    """

    if username is None:
        raise Exception('Please provide a username!')
    data = Data(config)
    data.execute(
        "DELETE FROM streamersettings WHERE username = :username LIMIT 1",
        {'username': username},
    )
    data.close()


def liststreamers(config: Dict[str, Any]) -> None:
    """
    Given a valid config pointing at a working DB, lists all active streamers on the network.
    """

    data = Data(config)
    cursor = data.execute("SELECT username FROM streamersettings")
    for result in cursor.fetchall():
        print(f"Streamer: {result['username']}")
    data.close()


def streamdescription(config: Dict[str, Any], username: Optional[str], description: Optional[str]) -> None:
    """
    Given a valid config and a valid streamer username, updates that streamer's active stream description
    to match the provided descrption.
    """

    if username is None:
        raise Exception('Please provide a username!')
    data = Data(config)
    data.execute(
        "UPDATE streamersettings SET description = :description WHERE username = :username",
        {'username': username, 'description': description},
    )
    data.close()


def streampassword(config: Dict[str, Any], username: Optional[str], password: Optional[str]) -> None:
    """
    Given a valid config and a valid streamer username, updates that streamer's viewer password for
    their stream. Note that this is not the same as the stream key, but something that you can set
    to force users to authenticate before watching.
    """

    if username is None:
        raise Exception('Please provide a username!')
    data = Data(config)
    data.execute(
        "UPDATE streamersettings SET streampass = :password WHERE username = :username",
        {'username': username, 'password': password},
    )
    data.close()


def addemote(config: Dict[str, Any], alias: Optional[str], uri: Optional[str]) -> None:
    """
    Given a valid config and an emote alias and a URI where that emote can be found, adds the emotes
    to the list of valid emotes/emojis on the server. The URI can be a valid full URI to a site,
    or can be a relative path to the root of your live instance pointing at static resources you host.
    """

    if alias is None:
        raise Exception('Please provide an alias!')
    if uri is None:
        raise Exception('Please provide a URI!')
    if ':' in alias:
        raise Exception('Aliases should not contain the ":" character!')
    data = Data(config)
    data.execute(
        "INSERT INTO emotes (`alias`, `uri`) VALUES (:alias, :uri)",
        {'alias': alias, 'uri': uri},
    )
    data.close()


def dropemote(config: Dict[str, Any], alias: Optional[str]) -> None:
    """
    Given a valid config and an emote alias, drops that emote from the list of emotes/emojis that
    are allowed on the server. Note that this cannot delete default emojis.
    """

    if alias is None:
        raise Exception('Please provide an alias!')
    if ':' in alias:
        raise Exception('Aliases should not contain the ":" character!')
    data = Data(config)
    data.execute(
        "DELETE FROM emotes WHERE alias = :alias LIMIT 1",
        {'alias': alias},
    )
    data.close()


def listemotes(config: Dict[str, Any]) -> None:
    """
    Given a valid config, lists all custom emotes that are supported on the server.
    """

    data = Data(config)
    cursor = data.execute("SELECT alias, uri FROM emotes")
    for result in cursor.fetchall():
        print(f"{result['alias']}: {result['uri']}")
    data.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="A utility for initializing and updating the streaming backend DB.")
    parser.add_argument(
        "operation",
        help="Operation to perform, options include 'create', 'generate', 'upgrade', 'addstreamer', 'dropstreamer', 'liststreamers', 'streamdescription', 'streampassword', 'addemote', 'dropemote', 'listemotes'.",
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
        help="Streamer username to use when adding or dropping a streamer and when updating the streamer description or password.",
        type=str,
    )
    parser.add_argument(
        "-k",
        "--key",
        help="Stream key in OBS or other streaming program when adding a streamer.",
        type=str,
    )
    parser.add_argument(
        "-a",
        "--alias",
        help="Alias to use for an emote when adding or dropping a custom emote.",
        type=str,
    )
    parser.add_argument(
        "-l",
        "--uri",
        help="URI of the emote when adding a custom emote.",
        type=str,
    )
    parser.add_argument(
        "-d",
        "--description",
        help="Provide the description for streamer page when setting the streamer description.",
        type=str,
    )
    parser.add_argument(
        "-p",
        "--password",
        help="Provide the password for streamer page when setting the streamer password.",
        type=str,
    )
    parser.add_argument(
        "-n",
        "--no-password",
        help="Unset the password for streamer page when setting the streamer password.",
        action="store_true",
    )

    parser.add_argument("-c", "--config", help="Core configuration. Defaults to config.yaml", type=str, default="config.yaml")
    args = parser.parse_args()

    config = yaml.safe_load(open(args.config))
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
        elif args.operation == "streamdescription":
            streamdescription(config, args.username, args.description)
        elif args.operation == "streampassword":
            streampassword(config, args.username, None if args.no_password else args.password)
        elif args.operation == "addemote":
            addemote(config, args.alias, args.uri)
        elif args.operation == "dropemote":
            dropemote(config, args.alias)
        elif args.operation == "listemotes":
            listemotes(config)
        else:
            raise Exception(f"Unknown operation '{args.operation}'")
    except DBCreateException as e:
        print(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
