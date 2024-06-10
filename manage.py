import argparse
import sys
import yaml
from typing import Any, Dict, Optional

from data import Data, DBCreateException


class CLIException(Exception):
    pass


class CommandException(Exception):
    pass


def create(config: Dict[str, Any]) -> None:
    """
    Given a config pointing at a valid MySQL DB, initializes that DB by creating all required tables.
    """

    data = Data(config)
    data.create()
    data.close()


def generate(config: Dict[str, Any], message: str, allow_empty: bool) -> None:
    """
    Given some changes to the table definitions in the SQL files of this repo, and a config pointing
    at a valid MySQL DB that has previously been initialized and then upgraded to the base revision
    of the repo before modification, generates a migration that will allow a production instance to
    auto-upgrade their DB to mirror your changes.
    """

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


def addstreamer(config: Dict[str, Any], username: str, key: str) -> None:
    """
    Given a valid config pointing at a working DB, a username and a key, add a streamer to the network
    identified by that username who will use that key to authenticate on their stream page and as their
    stream key when sending stream data to the RTMP endpoint.
    """

    data = Data(config)
    data.execute(
        "INSERT INTO streamersettings (`username`, `key`) VALUES (:username, :key)",
        {'username': username, 'key': key},
    )
    data.close()


def dropstreamer(config: Dict[str, Any], username: str) -> None:
    """
    Given a valid config pointing at a working DB and a username of an existing user, drop that streamer
    from the network.
    """

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


def streamdescription(config: Dict[str, Any], username: str, description: Optional[str]) -> None:
    """
    Given a valid config and a valid streamer username, updates that streamer's active stream description
    to match the provided descrption.
    """

    if not description:
        description = None
    data = Data(config)
    data.execute(
        "UPDATE streamersettings SET description = :description WHERE username = :username",
        {'username': username, 'description': description},
    )
    data.close()


def streampassword(config: Dict[str, Any], username: str, password: Optional[str]) -> None:
    """
    Given a valid config and a valid streamer username, updates that streamer's viewer password for
    their stream. Note that this is not the same as the stream key, but something that you can set
    to force users to authenticate before watching.
    """

    if not password:
        password = None
    data = Data(config)
    data.execute(
        "UPDATE streamersettings SET streampass = :password WHERE username = :username",
        {'username': username, 'password': password},
    )
    data.close()


def streamerkey(config: Dict[str, Any], username: str, key: Optional[str]) -> None:
    """
    Given a valid config and a valid streamer username, updates that streamer's key that they will use
    to authenticate with the RTMP endpoint.
    """

    if not key:
        raise CLIException("You must provide a valid stream key that isn't blank!")
    data = Data(config)
    data.execute(
        "UPDATE streamersettings SET `key` = :key WHERE username = :username",
        {'username': username, 'key': key},
    )
    data.close()


def addemote(config: Dict[str, Any], alias: str, uri: str) -> None:
    """
    Given a valid config and an emote alias and a URI where that emote can be found, adds the emotes
    to the list of valid emotes/emojis on the server. The URI can be a valid full URI to a site,
    or can be a relative path to the root of your live instance pointing at static resources you host.
    """

    if any(not (c.isalnum() or c == "_" or c == "-") for c in alias):
        raise CLIException('Aliases should contain only letters, numbers, underscores and dashes!')
    data = Data(config)
    try:
        data.execute(
            "INSERT INTO emotes (`alias`, `uri`) VALUES (:alias, :uri)",
            {'alias': alias, 'uri': uri},
        )
    except Exception as e:
        if "Duplicate entry" in str(e):
            raise CommandException(f"Alias {alias} already exists on this network!")
        else:
            raise
    finally:
        data.close()


def dropemote(config: Dict[str, Any], alias: str) -> None:
    """
    Given a valid config and an emote alias, drops that emote from the list of emotes/emojis that
    are allowed on the server. Note that this cannot delete default emojis.
    """

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
    cursor = data.execute("SELECT alias, uri FROM emotes ORDER BY alias")
    for result in cursor.fetchall():
        print(f"{result['alias']}: {result['uri']}")
    data.close()


def sendmessage(config: Dict[str, Any], username: str, messagetype: str, message: str) -> None:
    """
    Given a valid config, a username and a type, send a message as if that user had sent the message
    in a stream chat. Note that if nobody is in the room, the message will not get processed to be
    sent until somebody joins.
    """

    if messagetype not in {"normal", "action", "server"}:
        raise CLIException(f"Message type {messagetype} is not recognized!")

    data = Data(config)
    try:
        cursor = data.execute(
            "SELECT username FROM streamersettings WHERE username = :username LIMIT 1",
            {'username': username}
        )

        sent = False
        for result in cursor.fetchall():
            actual_username = result['username']
            data.execute(
                "INSERT INTO pendingmessages (`username`, `type`, `message`) VALUES (:username, :type, :message)",
                {'username': actual_username, 'type': messagetype, 'message': message},
            )

            # Successfully queued message.
            sent = True

        if not sent:
            raise CommandException(f"Could not find streamer {username} on this network!")
    finally:
        data.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="A utility for initializing and updating the streaming backend DB.")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.yaml",
        help="core configuration, used for determining what DB to connect to (defaults to config.yaml)",
    )
    commands = parser.add_subparsers(dest="operation")

    # Another subcommand here.
    database_parser = commands.add_parser(
        "database",
        help="modify backing DB for this network",
        description="Modify backing DB for this network.",
    )
    database_commands = database_parser.add_subparsers(dest="database")

    # No params for this one
    database_commands.add_parser(
        "create",
        help="create tables in fresh DB",
        description="Create tables in fresh DB.",
    )

    # Only a few params for this one
    generate_parser = database_commands.add_parser(
        "generate",
        help="generate migration from a DB and code delta",
        description="Generate migration from a DB and code delta.",
    )
    generate_parser.add_argument(
        "-m",
        "--message",
        required=True,
        type=str,
        help="message to use for auto-generated migration scripts, similar to a commit message",
    )
    generate_parser.add_argument(
        "-e",
        "--allow-empty",
        action='store_true',
        help="allow empty migration script to be generated (useful for creating data-only migrations)",
    )

    # No params for this one
    database_commands.add_parser(
        "upgrade",
        help="apply pending migrations to a DB",
        description="Apply pending migrations to a DB.",
    )

    # Another subcommand here.
    streamer_parser = commands.add_parser(
        "streamer",
        help="modify streamers on the network",
        description="Modify streamers on the network.",
    )
    streamer_commands = streamer_parser.add_subparsers(dest="streamer")

    # No params for this one
    streamer_commands.add_parser(
        "list",
        help="list all streamers",
        description="List all streamers.",
    )

    # A few params for this one
    addstreamer_parser = streamer_commands.add_parser(
        "add",
        help="add a streamer",
        description="Add a streamer.",
    )
    addstreamer_parser.add_argument(
        "-u",
        "--username",
        type=str,
        required=True,
        help="streamer username to add to the list of available streamers",
    )
    addstreamer_parser.add_argument(
        "-k",
        "--key",
        type=str,
        required=True,
        help="stream key in OBS or other streaming program that the streamer will use to authenticate with",
    )

    # A few params for this one
    dropstreamer_parser = streamer_commands.add_parser(
        "drop",
        help="drop a streamer",
        description="Drop a streamer.",
    )
    dropstreamer_parser.add_argument(
        "-u",
        "--username",
        type=str,
        required=True,
        help="streamer username to drop from the list of available streamers",
    )

    # A few params for this one
    streamkey_parser = streamer_commands.add_parser(
        "key",
        help="change a streamer's stream key",
        description="Change a streamer's stream key.",
    )
    streamkey_parser.add_argument(
        "-u",
        "--username",
        type=str,
        required=True,
        help="streamer username to modify the key for",
    )
    streamkey_parser.add_argument(
        "-k",
        "--key",
        type=str,
        required=True,
        help="stream key in OBS or other streaming program that the streamer will use to authenticate with",
    )

    # A few params for this one
    streamdescription_parser = streamer_commands.add_parser(
        "description",
        help="change or remove a streamer's stream description",
        description="Change or remove a streamer's stream description.",
    )
    streamdescription_parser.add_argument(
        "-u",
        "--username",
        type=str,
        required=True,
        help="streamer username to modify the description for",
    )
    streamdescription_parser.add_argument(
        "-d",
        "--description",
        type=str,
        default=None,
        help="the updated stream description for the streamer page when the specified streamer is live, leave out to unset",
    )

    # A few params for this one
    streampassword_parser = streamer_commands.add_parser(
        "password",
        help="change or remove a streamer's stream password",
        description="Change or remove a streamer's stream password.",
    )
    streampassword_parser.add_argument(
        "-u",
        "--username",
        type=str,
        required=True,
        help="streamer username to modify the description for",
    )
    streampassword_parser.add_argument(
        "-p",
        "--password",
        type=str,
        default=None,
        help="the updated stream password to access the stream page when the specified streamer is live, leave out to unset",
    )

    # Another subcommand here.
    emote_parser = commands.add_parser(
        "emote",
        help="modify custom emotes on the network",
        description="Modify custom emotes on the network.",
    )
    emote_commands = emote_parser.add_subparsers(dest="emote")

    # No params for this one
    emote_commands.add_parser(
        "list",
        help="list all custom emotes",
        description="List all custom emotes.",
    )

    # A few params for this one
    addemote_parser = emote_commands.add_parser(
        "add",
        help="add a custom emote",
        description="Add a custom emote.",
    )
    addemote_parser.add_argument(
        "-a",
        "--alias",
        type=str,
        required=True,
        help="alias to use for the emote you're adding, containing only alphanumberic characters, dashes and underscores",
    )
    addemote_parser.add_argument(
        "-l",
        "--uri",
        type=str,
        required=True,
        help="URI of the emote that you're adding, used when rendering the emote on the frontend",
    )

    # A few params for this one
    dropemote_parser = emote_commands.add_parser(
        "drop",
        help="drop a custom emote",
        description="Drop a custom emote.",
    )
    dropemote_parser.add_argument(
        "-a",
        "--alias",
        type=str,
        required=True,
        help="alias of the emote you're dropping, containing only alphanumberic characters, dashes and underscores",
    )

    # Another subcommand here.
    message_parser = commands.add_parser(
        "message",
        help="interact with messages on behalf of a streamer who is live",
        description="Interact with messages on behalf of a streamer who is live.",
    )
    message_commands = message_parser.add_subparsers(dest="message")

    # A few params for this one
    sendmessage_parser = message_commands.add_parser(
        "send",
        help="send a message on behalf of a streamer",
        description="Send a message on behalf of a streamer.",
    )
    sendmessage_parser.add_argument(
        "-u",
        "--username",
        type=str,
        required=True,
        help="streamer username for the stream the message will be sent to",
    )
    sendmessage_parser.add_argument(
        "-t",
        "--type",
        type=str,
        default='normal',
        choices=['normal', 'action', 'server'],
        help="type of message to send, defaulting to a normal message appearing as if the streamer typed it",
    )
    sendmessage_parser.add_argument(
        "-m",
        "--message",
        required=True,
        type=str,
        dest="contents",
        help="actual message to send to the chat of the streamer",
    )

    args = parser.parse_args()

    config = yaml.safe_load(open(args.config))
    config['database']['engine'] = Data.create_engine(config)
    try:
        if args.operation is None:
            raise CLIException("Unuspecified operation!")

        elif args.operation == "database":
            if args.database is None:
                raise CLIException("Unuspecified database operation!")
            elif args.database == "create":
                create(config)
            elif args.database == "generate":
                generate(config, args.message, args.allow_empty)
            elif args.database == "upgrade":
                upgrade(config)
            else:
                raise CLIException(f"Unknown database operation '{args.database}'")

        elif args.operation == "streamer":
            if args.streamer is None:
                raise CLIException("Unuspecified streamer operation!")
            elif args.streamer == "add":
                addstreamer(config, args.username, args.key)
            elif args.streamer == "drop":
                dropstreamer(config, args.username)
            elif args.streamer == "key":
                streamerkey(config, args.username, args.key)
            elif args.streamer == "list":
                liststreamers(config)
            elif args.streamer == "description":
                streamdescription(config, args.username, args.description)
            elif args.streamer == "password":
                streampassword(config, args.username, args.password)
            else:
                raise CLIException(f"Unknown streamer operation '{args.streamer}'")

        elif args.operation == "emote":
            if args.emote is None:
                raise CLIException("Unuspecified emote operation!")
            elif args.emote == "add":
                addemote(config, args.alias, args.uri)
            elif args.emote == "drop":
                dropemote(config, args.alias)
            elif args.emote == "list":
                listemotes(config)
            else:
                raise CLIException(f"Unknown emote operation '{args.emote}'")

        elif args.operation == "message":
            if args.message is None:
                raise CLIException("Unuspecified message operation!")
            elif args.message == "send":
                sendmessage(config, args.username, args.type, args.contents)
            else:
                raise CLIException(f"Unknown message operation '{args.message}'")

        else:
            raise CLIException(f"Unknown operation '{args.operation}'")
    except CLIException as e:
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)
    except CommandException as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except DBCreateException as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
