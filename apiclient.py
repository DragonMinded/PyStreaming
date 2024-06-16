import argparse
import requests
import sys
from requests.auth import HTTPBasicAuth
from typing import List, Optional


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

    args = parser.parse_args()

    try:
        if args.operation is None:
            raise CLIException("Unuspecified operation!")

        if args.operation == "getinfo":
            info = get_info(args.domain, args.username, args.key)
            print(info)

        sys.exit(0)
    except CLIException as e:
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)
