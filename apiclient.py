import argparse
import requests
import sys
from requests.auth import HTTPBasicAuth
from typing import Dict, List, Optional, Union


class APIException(Exception):
    pass


class StreamInfo:
    def __init__(
        self, username: str, password: Optional[str], description: str, members: List[str], live: bool, viewers: int
    ) -> None:
        self.username = username
        self.password = password
        self.description = description
        self.members = members
        self.live = live
        self.viewers = viewers

    def __repr__(self) -> str:
        return f"StreamInfo(username={self.username!r}, password={self.password!r}, description={self.description!r}, members={self.members!r}, live={self.live!r}, viewers={self.viewers!r})"


def get_info(domain: str, streamer: str, streamkey: str) -> StreamInfo:
    resp = requests.get(f"{domain}/api/info", auth=HTTPBasicAuth(streamer, streamkey))
    if resp.status_code == 401:
        raise APIException(f"You are not authorized to make requests on behalf of {streamer}")
    if resp.status_code != 200:
        raise APIException("Server returned error response")

    jsondata = resp.json()

    return StreamInfo(
        username=str(jsondata["username"]),
        password=str(jsondata["streampass"]) if jsondata["streampass"] else None,
        description=str(jsondata["description"]),
        members=[str(s) for s in jsondata["members"]],
        live=bool(jsondata["live"]),
        viewers=int(jsondata["viewers"]),
    )


class __SentinelValue:
    pass


# So we can allow setting null to unset a value, versus leaving unspecified to not update a value.
__sentinel_value = __SentinelValue()


def update_info(
    domain: str,
    streamer: str,
    streamkey: str,
    *,
    description: Optional[Union[str, __SentinelValue]] = __sentinel_value,
    password: Optional[Union[str, __SentinelValue]] = __sentinel_value,
) -> None:
    data: Dict[str, object] = {}
    if not isinstance(description, __SentinelValue):
        data["description"] = description or ""
    if not isinstance(password, __SentinelValue):
        data["streampass"] = password

    resp = requests.patch(f"{domain}/api/info", auth=HTTPBasicAuth(streamer, streamkey), json=data)
    if resp.status_code == 401:
        raise APIException(f"You are not authorized to make requests on behalf of {streamer}")
    if resp.status_code != 200:
        raise APIException("Server returned error response")


def send_message(
    domain: str,
    streamer: str,
    streamkey: str,
    *,
    messagetype: str = "normal",
    message: str = "",
) -> None:
    if messagetype not in {"normal", "action", "server"}:
        raise APIException(f"Message type {messagetype} is not recognized!")
    if not message:
        raise APIException("Cannot send an empty message!")

    data: Dict[str, object] = {
        "type": messagetype,
        "message": message,
    }
    resp = requests.post(f"{domain}/api/messages", auth=HTTPBasicAuth(streamer, streamkey), json=data)
    if resp.status_code == 401:
        raise APIException(f"You are not authorized to make requests on behalf of {streamer}")
    if resp.status_code != 200:
        raise APIException("Server returned error response")


class CLIException(Exception):
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Example API client with various operations.")
    parser.add_argument(
        "domain",
        metavar="DOMAIN",
        type=str,
        help="Domain of the streaming instance, given in https://my.domain.here notation.",
    )
    parser.add_argument(
        "-u",
        "--username",
        required=True,
        type=str,
        help="streamer username to fetch information for",
    )
    parser.add_argument(
        "-k",
        "--key",
        type=str,
        required=True,
        help="stream key that the streamer uses to authenticate with",
    )

    commands = parser.add_subparsers(dest="operation")

    # Get info subcommand.
    getinfo_parser = commands.add_parser(
        "getinfo",
        help="get info from a remote streaming server",
        description="Get info from a remote streaming server.",
    )

    # Set description subcommand.
    setdescription_parser = commands.add_parser(
        "setdescription",
        help="update the description on a remote streaming server",
        description="Update the description on a remote streaming server.",
    )
    setdescription_parser.add_argument(
        "-d",
        "--description",
        type=str,
        required=True,
        help="the description to update the stream to",
    )

    # Set viewer password subcommand.
    setpassword_parser = commands.add_parser(
        "setpassword",
        help="update the viewer password on a remote streaming server",
        description="Update the viewer password on a remote streaming server.",
    )
    setpassword_parser.add_argument(
        "-p",
        "--password",
        type=str,
        required=True,
        help="the viewer password to update the stream to",
    )

    # Send a message on behalf of the streamer.
    sendmessage_parser = commands.add_parser(
        "sendmessage",
        help="send a message on behalf of a streamer",
        description="Send a message on behalf of a streamer.",
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

    try:
        if args.operation is None:
            raise CLIException("Unuspecified operation!")

        if args.operation == "getinfo":
            info = get_info(args.domain, args.username, args.key)
            print(info)

        elif args.operation == "setdescription":
            update_info(args.domain, args.username, args.key, description=args.description)
            print("Stream description updated!")

        elif args.operation == "setpassword":
            update_info(args.domain, args.username, args.key, password=args.password or None)
            print("Stream viewer password updated!")

        elif args.operation == "sendmessage":
            send_message(args.domain, args.username, args.key, messagetype=args.type, message=args.contents)
            print("Message sent on behalf of streamer!")

        else:
            raise CLIException(f"Unrecognized operation {args.operation}")

        sys.exit(0)
    except CLIException as e:
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)
