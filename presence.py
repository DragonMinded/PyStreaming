from threading import Lock
from typing import Any, Dict, List, Optional

from helpers import now


class SocketInfo:
    def __init__(self, sid: Any, ip: str, streamer: str, username: str, admin: bool, moderator: bool, muted: bool, color: int) -> None:
        self.sid = sid
        self.ip = ip
        self.streamer = streamer
        self.username = username
        self.admin = admin
        self.moderator = moderator
        self.muted = muted
        self.color = color

    @property
    def htmlcolor(self) -> str:
        color = hex(self.color)[2:]
        if len(color) < 6:
            color = ('0' * (6 - len(color))) + color
        return '#' + color

    @property
    def type(self) -> str:
        """
        Returns the type of user, given the socket info of the user. Valid types include
        "admim", "moderator" and "normal" users.
        """

        if self.admin:
            return "admin"
        elif self.moderator:
            return "moderator"
        else:
            return "normal"


class PresenceInfo:
    def __init__(self, sid: Any, streamer: Optional[str]) -> None:
        self.sid = sid
        self.streamer = streamer
        self.timestamp = now()


presence_lock: Lock = Lock()
socket_to_info: Dict[Any, SocketInfo] = {}
socket_to_presence: Dict[Any, PresenceInfo] = {}


def users_in_room(streamer: str) -> List[Dict[str, str]]:
    """
    Looks up all the users in a given room, where a room is dictated by the streamer handle.
    """

    return [{'username': i.username, 'type': i.type, 'color': i.htmlcolor} for i in socket_to_info.values() if i.streamer == streamer]


def stream_count(streamer: str) -> int:
    """
    Looks up the count of active viewers on the stream, as dictated by anyone who has interacted with the
    stream in any manner (pulling info, chat connection, etc) in the last 30 seconds.
    """

    oldest = now() - 30
    with presence_lock:
        return len([None for x in socket_to_presence.values() if x.streamer == streamer and x.timestamp >= oldest])
