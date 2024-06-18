from abc import ABC
import json
from typing import Dict, List, Optional, Type

from data import Data


class Event(ABC):
    __TYPE__: str

    def __init__(self, eid: Optional[int], timestamp: int, streamer: str, etype: str, meta: Dict[str, object]) -> None:
        self.id = eid
        self.timestamp = timestamp
        self.streamer = streamer
        self.type = etype
        self.meta = meta

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "Event":
        raise NotImplementedError("Implement in subclass!")


class StartStreamingEvent(Event):
    __TYPE__ = "start_streaming"

    def __init__(self, timestamp: int, streamer: str, description: str, password: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"description": description, "password": password})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "StartStreamingEvent":
        event = StartStreamingEvent(
            timestamp,
            streamer,
            str(meta["description"]),
            str(meta["password"]),
        )
        event.id = eid
        return event


class StopStreamingEvent(Event):
    __TYPE__ = "stop_streaming"

    def __init__(self, timestamp: int, streamer: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "StopStreamingEvent":
        event = StopStreamingEvent(
            timestamp,
            streamer,
        )
        event.id = eid
        return event


class SendMessageEvent(Event):
    __TYPE__ = "send_message"

    def __init__(self, timestamp: int, streamer: str, name: str, message: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"name": name, "message": message})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "SendMessageEvent":
        event = SendMessageEvent(
            timestamp,
            streamer,
            str(meta["name"]),
            str(meta["message"]),
        )
        event.id = eid
        return event


class SendDrawingEvent(Event):
    __TYPE__ = "send_drawing"

    def __init__(self, timestamp: int, streamer: str, name: str, drawing: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"name": name, "drawing": drawing})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "SendDrawingEvent":
        event = SendDrawingEvent(
            timestamp,
            streamer,
            str(meta["name"]),
            str(meta["drawing"]),
        )
        event.id = eid
        return event


class SendActionEvent(Event):
    __TYPE__ = "send_action"

    def __init__(self, timestamp: int, streamer: str, name: str, action: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"name": name, "action": action})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "SendActionEvent":
        event = SendActionEvent(
            timestamp,
            streamer,
            str(meta["name"]),
            str(meta["action"]),
        )
        event.id = eid
        return event


class SendBroadcastEvent(Event):
    __TYPE__ = "send_broadcast"

    def __init__(self, timestamp: int, streamer: str, broadcast: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"broadcast": broadcast})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "SendBroadcastEvent":
        event = SendBroadcastEvent(
            timestamp,
            streamer,
            str(meta["broadcast"]),
        )
        event.id = eid
        return event


class JoinChatEvent(Event):
    __TYPE__ = "join_chat"

    def __init__(self, timestamp: int, streamer: str, name: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"name": name})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "JoinChatEvent":
        event = JoinChatEvent(
            timestamp,
            streamer,
            str(meta["name"]),
        )
        event.id = eid
        return event


class LeaveChatEvent(Event):
    __TYPE__ = "leave_chat"

    def __init__(self, timestamp: int, streamer: str, name: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"name": name})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "LeaveChatEvent":
        event = LeaveChatEvent(
            timestamp,
            streamer,
            str(meta["name"]),
        )
        event.id = eid
        return event


class ChangeNameEvent(Event):
    __TYPE__ = "change_name"

    def __init__(self, timestamp: int, streamer: str, oldname: str, newname: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"oldname": oldname, "newname": newname})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "ChangeNameEvent":
        event = ChangeNameEvent(
            timestamp,
            streamer,
            str(meta["oldname"]),
            str(meta["newname"]),
        )
        event.id = eid
        return event


class ViewerCountEvent(Event):
    __TYPE__ = "viewer_count"

    def __init__(self, timestamp: int, streamer: str, viewers: int) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"viewers": viewers})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "ViewerCountEvent":
        event = ViewerCountEvent(
            timestamp,
            streamer,
            int(str(meta["viewers"])),
        )
        event.id = eid
        return event


class ModUserEvent(Event):
    __TYPE__ = "mod_user"

    def __init__(self, timestamp: int, streamer: str, operator: str, name: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"operator": operator, "name": name})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "ModUserEvent":
        event = ModUserEvent(
            timestamp,
            streamer,
            str(meta["operator"]),
            str(meta["name"]),
        )
        event.id = eid
        return event


class DemodUserEvent(Event):
    __TYPE__ = "demod_user"

    def __init__(self, timestamp: int, streamer: str, operator: str, name: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"operator": operator, "name": name})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "DemodUserEvent":
        event = DemodUserEvent(
            timestamp,
            streamer,
            str(meta["operator"]),
            str(meta["name"]),
        )
        event.id = eid
        return event


class MuteUserEvent(Event):
    __TYPE__ = "mute_user"

    def __init__(self, timestamp: int, streamer: str, operator: str, name: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"operator": operator, "name": name})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "MuteUserEvent":
        event = MuteUserEvent(
            timestamp,
            streamer,
            str(meta["operator"]),
            str(meta["name"]),
        )
        event.id = eid
        return event


class UnmuteUserEvent(Event):
    __TYPE__ = "unmute_user"

    def __init__(self, timestamp: int, streamer: str, operator: str, name: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"operator": operator, "name": name})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "UnmuteUserEvent":
        event = UnmuteUserEvent(
            timestamp,
            streamer,
            str(meta["operator"]),
            str(meta["name"]),
        )
        event.id = eid
        return event


class SetDescriptionEvent(Event):
    __TYPE__ = "set_description"

    def __init__(self, timestamp: int, streamer: str, description: str) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"description": description})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "SetDescriptionEvent":
        event = SetDescriptionEvent(
            timestamp,
            streamer,
            str(meta["description"]),
        )
        event.id = eid
        return event


class SetViewerPasswordEvent(Event):
    __TYPE__ = "set_viewer_password"

    def __init__(self, timestamp: int, streamer: str, password: Optional[str]) -> None:
        super().__init__(None, timestamp, streamer, self.__TYPE__, {"password": password})

    @staticmethod
    def __from_db__(
        eid: int,
        timestamp: int,
        streamer: str,
        meta: Dict[str, object]
    ) -> "SetViewerPasswordEvent":
        event = SetViewerPasswordEvent(
            timestamp,
            streamer,
            str(meta["password"]) if meta["password"] else None,
        )
        event.id = eid
        return event


__VALID_EVENTS: List[Type[Event]] = [
    StartStreamingEvent,
    StopStreamingEvent,
    ViewerCountEvent,
    SetDescriptionEvent,
    SetViewerPasswordEvent,
    JoinChatEvent,
    ChangeNameEvent,
    LeaveChatEvent,
    SendMessageEvent,
    SendDrawingEvent,
    SendActionEvent,
    SendBroadcastEvent,
    ModUserEvent,
    DemodUserEvent,
    MuteUserEvent,
    UnmuteUserEvent,
]


def insert_event(data: Data, event: Event) -> None:
    if event.id is not None:
        raise Exception("Cannot re-insert existing event!")

    cursor = data.execute(
        "INSERT INTO events (`timestamp`, `username`, `type`, `meta`) VALUES (:ts, :streamer, :type, :meta)",
        {'ts': event.timestamp, 'streamer': event.streamer, 'type': event.type, 'meta': json.dumps(event.meta)}
    )
    event.id = cursor.lastrowid


def get_events(
    data: Data,
    *,
    streamer: str,
    type: Optional[str] = None,
    after: Optional[Event] = None,
    limit: Optional[int] = None,
) -> List[Event]:
    sql = "SELECT * FROM events WHERE streamer = :streamer"
    params: Dict[str, object] = {
        'streamer': streamer,
    }

    if type is not None:
        sql += " AND type = :type"
        params['type'] = type
    if after is not None:
        if after.id is None:
            raise Exception("Cannot select after an event that hasn't been persisted!")
        sql += " AND id > :id"
        params['id'] = after.id

    sql += " ORDER BY id DESC"
    if limit:
        sql += " LIMIT :limit"
        params['limit'] = limit

    results: List[Event] = []

    cursor = data.execute(sql, params)
    for row in cursor:
        etype = row["type"]

        for cls in __VALID_EVENTS:
            if cls.__TYPE__ == etype:
                results.append(cls.__from_db__(
                    int(row["id"]),
                    int(row["timestamp"]),
                    str(row["username"]),
                    json.loads(row["meta"]),
                ))
                break
            else:
                raise Exception(f"Invalid type {etype} found in database!")

    return results
