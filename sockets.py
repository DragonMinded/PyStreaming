import urllib.request
from flask_socketio import join_room  # type: ignore
from PIL import Image
from typing import Any, Dict, List, Optional, Set

from app import socketio, request
from events import (
    JoinChatEvent,
    ChangeNameEvent,
    LeaveChatEvent,
    ViewerCountEvent,
    SendMessageEvent,
    SendDrawingEvent,
    SendActionEvent,
    SendBroadcastEvent,
    insert_event,
)
from helpers import (
    PICTOCHAT_IMAGE_WIDTH,
    PICTOCHAT_IMAGE_HEIGHT,
    emotes,
    first_quality,
    get_color,
    message_length,
    mysql,
    now,
    stream_live,
)
from presence import (
    SocketInfo,
    PresenceInfo,
    presence_lock,
    socket_to_info,
    socket_to_presence,
    stream_count,
    users_in_room,
)


background_thread: Optional[object] = None


def background_thread_proc() -> None:
    """
    The background polling thread that manages asynchronous messages from the database.
    """

    # Grab the initial list of emoji that are supported so that we can delta it occasionally and
    # inform clients of emoji changes on the server. Technically there could be a race where we
    # add an emote right after somebody loads the page but before the JS connects to us, but the
    # likelihood of that is small, so we will live with the bug.
    cursor = mysql().execute(
        "SELECT alias, uri FROM emotes",
    )
    validemotes = {f":{result['alias']}:": result['uri'] for result in cursor}
    last_update = now()

    # Track our known streamer viewcounts.
    viewcounts: Dict[str, int] = {}

    while True:
        # Just yield to the async system.
        socketio.sleep(1.0)

        # Our connection for this loop.
        data = mysql()

        # Look up any pending messages that need to be sent.
        streamers = set(s.streamer for s in socket_to_info.values() if s.streamer)
        usernames = {s.streamer: s.username for s in socket_to_info.values() if s.admin}
        colors = {s.streamer: s.htmlcolor for s in socket_to_info.values() if s.admin}

        cursor = data.execute("SELECT id, username, type, message FROM pendingmessages")
        for result in cursor:
            delid = result['id']
            username = result['username']
            streamer = username.lower()
            msgtype = result['type']
            message = result['message']

            if streamer not in streamers:
                continue

            # If they're actually chatting, use the name they're currently set to. Otherwise
            # default to their stream username. Also, default to their currently set color or
            # use black as the default.
            actual_name = usernames.get(streamer, username)
            actual_color = colors.get(streamer, '#000000')

            if msgtype == "server":
                insert_event(
                    data,
                    SendBroadcastEvent(
                        now(),
                        streamer,
                        message,
                    )
                )

                socketio.emit(
                    'server',
                    {'msg': message},
                    room=streamer,
                )
            elif msgtype == "action":
                insert_event(
                    data,
                    SendActionEvent(
                        now(),
                        streamer,
                        actual_name,
                        emotes(message),
                    )
                )

                socketio.emit(
                    'action received',
                    {
                        'username': actual_name,
                        'type': 'admin',
                        'color': actual_color,
                        'message': emotes(message),
                    },
                    room=streamer,
                )
            elif msgtype == "normal":
                insert_event(
                    data,
                    SendMessageEvent(
                        now(),
                        streamer,
                        actual_name,
                        emotes(message),
                    )
                )

                socketio.emit(
                    'message received',
                    {
                        'username': actual_name,
                        'type': 'admin',
                        'color': actual_color,
                        'message': emotes(message),
                    },
                    room=streamer,
                )

            data.execute("DELETE FROM pendingmessages WHERE id = :id LIMIT 1", {'id': delid})

        # Figure out if we need to log an analytics event (viewer count changed).
        alltracked = set(streamers)
        alltracked.update(viewcounts.keys())
        alltracked.update(p.streamer for p in socket_to_presence.values() if p.streamer)
        for streamer in alltracked:
            cursor = data.execute(
                "SELECT `key` FROM streamersettings WHERE username = :username",
                {"username": streamer},
            )
            if cursor.rowcount == 1:
                result = cursor.fetchone()

                # Figure out if the stream itself is live.
                live = stream_live(result['key'], first_quality())

                # Grab viewer count, active chatters.
                viewers = stream_count(streamer) if live else 0
                oldviewers = viewcounts.get(streamer, -1)

                if viewers != oldviewers:
                    viewcounts[streamer] = viewers
                    insert_event(
                        data,
                        ViewerCountEvent(
                            now(),
                            streamer,
                            viewers,
                        )
                    )

        if now() - last_update >= 5:
            # Delta our emojis and send the deltas to clients.
            cursor = data.execute(
                "SELECT alias, uri FROM emotes",
            )

            updated: Set[str] = set()
            for result in cursor:
                key = f":{result['alias']}:"
                uri = result['uri']

                if key not in validemotes:
                    # This was an addition.
                    print(f"Broadcasting new emote {key} to all connected clients.")
                    validemotes[key] = uri

                    # Emit to all clients, so don't provide a room.
                    socketio.emit(
                        'add emote',
                        {'key': key, 'uri': uri},
                    )

                updated.add(key)

            for existing in list(validemotes.keys()):
                if existing not in updated:
                    # This was a deletion.
                    print(f"Broadcasting deleted emote {existing} to all connected clients.")
                    del validemotes[existing]

                    # Emit to all clients, so don't provide a room.
                    socketio.emit(
                        'remove emote',
                        {'key': existing},
                    )

            last_update = now()

        with presence_lock:
            # Clean up orphaned watchers.
            sids = list(socket_to_presence.keys())
            oldest = now() - 30

            for sid in sids:
                if socket_to_presence[sid].timestamp < oldest:
                    del socket_to_presence[sid]

            # If there's nobody left watching, shut ourselves down to save on DB accesses.
            if not socket_to_presence:
                print("Shutting down polling thread due to no more client sockets.")

                global background_thread
                background_thread = None

                return


def update_presence(sid: Any, streamer: Optional[str]) -> None:
    """
    Given a stream SID and a streamer, update the presence info for the purpose of counting
    connected SIDs as well as stream viewers.
    """

    with presence_lock:
        socket_to_presence[sid] = PresenceInfo(sid, streamer)

        global background_thread
        if background_thread is None:
            print("Starting polling thread due to first client socket connection.")
            background_thread = socketio.start_background_task(background_thread_proc)


def delete_presence(sid: Any) -> None:
    """
    Given a stream SID, delete the presence info for the purpose of counting connected SIDs.
    """

    with presence_lock:
        if request.sid in socket_to_presence:
            del socket_to_presence[request.sid]


@socketio.on('connect')  # type: ignore
def connect() -> None:
    if request.sid in socket_to_info:
        del socket_to_info[request.sid]

    # Make sure we track this client so we don't get a premature hang-up.
    update_presence(request.sid, None)


@socketio.on('disconnect')  # type: ignore
def disconnect() -> None:
    if request.sid in socket_to_info:
        info = socket_to_info[request.sid]
        del socket_to_info[request.sid]

        insert_event(
            mysql(),
            LeaveChatEvent(
                now(),
                info.streamer,
                info.username,
            )
        )

        socketio.emit('disconnected', {'username': info.username, 'type': info.type, 'color': info.htmlcolor, 'users': users_in_room(info.streamer)}, room=info.streamer)

    # Explicitly kill the presence since we know they're gone.
    delete_presence(request.sid)


@socketio.on('presence')  # type: ignore
def handle_presence(json: Dict[str, Any], methods: List[str] = ['GET', 'POST']) -> None:
    if 'streamer' not in json:
        return

    # Update user presence information
    streamer = json['streamer'].lower()
    update_presence(request.sid, streamer)


@socketio.on('login')  # type: ignore
def handle_login(json: Dict[str, Any], methods: List[str] = ['GET', 'POST']) -> None:
    if request.sid in socket_to_info:
        socketio.emit('error', {'msg': 'SID already taken?'}, room=request.sid)
        return

    if 'username' not in json:
        socketio.emit('error', {'msg': 'Username mssing from JSON?'}, room=request.sid)
        return

    if 'streamer' not in json:
        socketio.emit('error', {'msg': 'Streamer mssing from JSON?'}, room=request.sid)
        return

    if len(json['username']) == 0:
        socketio.emit('error', {'msg': 'Username cannot be blank'}, room=request.sid)
        return

    data = mysql()
    if message_length(data, json['username']) > 20:
        socketio.emit('error', {'msg': 'Username cannot be that long'}, room=request.sid)
        return

    streamer = json['streamer'].lower()
    username = json['username']

    first_to_join = True
    for user in users_in_room(streamer):
        first_to_join = False
        if user['username'].lower() == username.lower():
            socketio.emit('error', {'msg': 'Username is already taken'}, room=request.sid)
            return

    color = get_color(json['color'].strip().lower()) or 0
    key = json.get('key', None)

    # Update user presence information
    update_presence(request.sid, streamer)

    cursor = data.execute(
        "SELECT `username`, `key` FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        socketio.emit('error', {'msg': 'Streamer does not exist'}, room=request.sid)
        return

    admin = False
    if username.lower() == streamer:
        result = cursor.fetchone()

        if key is None:
            socketio.emit('login key required', {'username': result['username']}, room=request.sid)
            return

        if key != result["key"]:
            socketio.emit('error', {'msg': 'Invalid password!'}, room=request.sid)
            return

        username = result['username']
        admin = True

    for _, existing in socket_to_info.items():
        if existing.streamer != streamer:
            # Not the right room
            continue

        if existing.username.lower() == json['username'].lower():
            socketio.emit('error', {'msg': 'Username is taken'}, room=request.sid)
            return

    # If we have any pending API-queued messages for this streamer and this is the first chatter to
    # join, blow all those pending messages away. This is so that the first person to join a room
    # that was previously empty doesn't get jumpscaped with a ton of stale messages.
    if first_to_join:
        data.execute("DELETE FROM pendingmessages WHERE username = :streamer", {'streamer': streamer})

    socket_to_info[request.sid] = SocketInfo(request.sid, str(request.remote_addr), streamer, json['username'], admin, False, False, color)
    join_room(streamer)
    socketio.emit('login success', {'username': json['username']}, room=request.sid)
    socketio.emit('connected', {'username': json['username'], 'type': socket_to_info[request.sid].type, 'color': socket_to_info[request.sid].htmlcolor, 'users': users_in_room(streamer)}, room=streamer)

    insert_event(
        data,
        JoinChatEvent(
            now(),
            streamer,
            json['username']
        )
    )

    if admin:
        socketio.emit('server', {'msg': 'You have admin rights.'}, room=request.sid)


@socketio.on('message')  # type: ignore
def handle_message(json: Dict[str, Any], methods: List[str] = ['GET', 'POST']) -> None:
    if 'message' not in json:
        socketio.emit('error', {'msg': 'Message mssing from JSON?'}, room=request.sid)
        return

    if len(json['message']) == 0:
        socketio.emit('warning', {'msg': 'Message cannot be blank'}, room=request.sid)
        return

    if request.sid not in socket_to_info:
        socketio.emit('error', {'msg': 'User is not authenticated?'}, room=request.sid)
        return

    # Update user presence information
    update_presence(request.sid, socket_to_info[request.sid].streamer)

    # Our data connection for various operations.
    data = mysql()

    message = json['message'].strip()
    if message[0] == "/":
        # Command of some sort
        if ' ' in message:
            command, message = message.split(' ', 1)
        else:
            command = message
            message = ""

        if command in ["/say"]:
            if socket_to_info[request.sid].muted:
                socketio.emit(
                    'server',
                    {'msg': "You are muted!"},
                    room=request.sid,
                )
            else:
                # Just a say message
                insert_event(
                    data,
                    SendMessageEvent(
                        now(),
                        socket_to_info[request.sid].streamer,
                        socket_to_info[request.sid].username,
                        emotes(message),
                    )
                )

                socketio.emit(
                    'message received',
                    {
                        'username': socket_to_info[request.sid].username,
                        'type': socket_to_info[request.sid].type,
                        'color': socket_to_info[request.sid].htmlcolor,
                        'message': emotes(message),
                    },
                    room=socket_to_info[request.sid].streamer,
                )
        elif command in ["/me", "/action", "/describe"]:
            if socket_to_info[request.sid].muted:
                socketio.emit(
                    'server',
                    {'msg': "You are muted!"},
                    room=request.sid,
                )
            else:
                # An action message
                insert_event(
                    data,
                    SendActionEvent(
                        now(),
                        socket_to_info[request.sid].streamer,
                        socket_to_info[request.sid].username,
                        emotes(message),
                    )
                )

                socketio.emit(
                    'action received',
                    {
                        'username': socket_to_info[request.sid].username,
                        'type': socket_to_info[request.sid].type,
                        'color': socket_to_info[request.sid].htmlcolor,
                        'message': emotes(message),
                    },
                    room=socket_to_info[request.sid].streamer,
                )
        elif command in ["/color", "/setcolor"]:
            if socket_to_info[request.sid].muted:
                socketio.emit(
                    'server',
                    {'msg': "You are muted!"},
                    room=request.sid,
                )
            else:
                # Set the color of your name
                color = get_color(message.strip().lower())

                if not color:
                    socketio.emit(
                        'server',
                        {'msg': f'Invalid color {message} specified, try a color name, an HTML color like #ff00ff or "random" for a random color.'},
                        room=request.sid,
                    )
                else:
                    socket_to_info[request.sid].color = color
                    socketio.emit(
                        'action received',
                        {
                            'username': socket_to_info[request.sid].username,
                            'type': socket_to_info[request.sid].type,
                            'color': socket_to_info[request.sid].htmlcolor,
                            'message': 'changed their color!',
                        },
                        room=socket_to_info[request.sid].streamer,
                    )
                    socketio.emit(
                        'return color',
                        {'color': socket_to_info[request.sid].htmlcolor},
                        room=request.sid,
                    )
        elif command in ["/name", "/nick"]:
            if socket_to_info[request.sid].muted:
                socketio.emit(
                    'server',
                    {'msg': "You are muted!"},
                    room=request.sid,
                )
            else:
                # Set a new name
                name = message.strip()

                if message_length(data, name) > 20:
                    socketio.emit(
                        'server',
                        {'msg': 'Too long of a name specified, try a different name.'},
                        room=request.sid,
                    )
                else:
                    for user in users_in_room(socket_to_info[request.sid].streamer):
                        if user['username'].lower() == name.lower():
                            socketio.emit(
                                'server',
                                {'msg': 'Name has already been taken, try a different name.'},
                                room=request.sid,
                            )
                            break
                    else:
                        if not name:
                            socketio.emit(
                                'server',
                                {'msg': 'Invalid name specified, try a different name.'},
                                room=request.sid,
                            )
                        else:
                            old = socket_to_info[request.sid].username
                            socket_to_info[request.sid].username = name

                            insert_event(
                                data,
                                ChangeNameEvent(
                                    now(),
                                    socket_to_info[request.sid].streamer,
                                    old,
                                    socket_to_info[request.sid].username,
                                )
                            )

                            socketio.emit(
                                'rename',
                                {
                                    'newname': socket_to_info[request.sid].username,
                                    'oldname': old,
                                    'type': socket_to_info[request.sid].type,
                                    'color': socket_to_info[request.sid].htmlcolor,
                                    'users': users_in_room(socket_to_info[request.sid].streamer),
                                },
                                room=socket_to_info[request.sid].streamer,
                            )
        elif command in ["/help"]:
            messages = [
                "The following commands are recognized:",
                "/help - show this message",
                "/users - show the currently chatting users",
                "/me <action> - perform an action",
                "/color <color> - set the color of your name in chat",
                "/name <new name> - change your name to a new one",
            ]
            if socket_to_info[request.sid].admin:
                messages.append("/settings - display all stream settings")
                messages.append("/description <text> - set the stream description")
                messages.append("/password [<text>] - set or unset the stream password")
                messages.append("/mod <user> - grant moderator privileges to user")
                messages.append("/demod <user> - revoke moderator privileges to user")
            if socket_to_info[request.sid].admin or socket_to_info[request.sid].moderator:
                messages.append("/mute <user> - mute user")
                messages.append("/unmute <user> - unmute user")
                messages.append("/rename <user> <new name> - rename user")

            for message in messages:
                socketio.emit(
                    'server',
                    {'msg': message},
                    room=request.sid,
                )
        elif command in ["/users", "/userlist", "/names"]:
            socketio.emit(
                'userlist',
                {'users': users_in_room(socket_to_info[request.sid].streamer)},
                room=request.sid,
            )
        elif command in ["/settings"]:
            if not socket_to_info[request.sid].admin:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                    room=request.sid,
                )
                return

            streamer = socket_to_info[request.sid].streamer
            cursor = data.execute(
                "SELECT `description`, `streampass` FROM streamersettings WHERE `username` = :streamer",
                {"streamer": streamer}
            )
            if cursor.rowcount != 1:
                socketio.emit(
                    'server',
                    {'msg': "Error looking up settings!"},
                    room=request.sid,
                )
            else:
                result = cursor.fetchone()
                if result['streampass']:
                    socketio.emit(
                        'server',
                        {'msg': f"Description: {result['description']}"},
                        room=request.sid,
                    )
                else:
                    socketio.emit(
                        'server',
                        {'msg': "No stream description"},
                        room=request.sid,
                    )
                if result['streampass']:
                    socketio.emit(
                        'server',
                        {'msg': f"Stream password: {result['streampass']}"},
                        room=request.sid,
                    )
                else:
                    socketio.emit(
                        'server',
                        {'msg': "No stream password"},
                        room=request.sid,
                    )
        elif command in ["/mute", "/quiet"]:
            if not (socket_to_info[request.sid].admin or socket_to_info[request.sid].moderator):
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                    room=request.sid,
                )
                return

            message = message.strip().lower()
            for sinfo in socket_to_info.values():
                if sinfo.username.lower() == message and sinfo.streamer == socket_to_info[request.sid].streamer:
                    if sinfo.admin:
                        # Stop admins from softlocking themselves, stop mods from muting admin.
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' cannot be muted."},
                            room=request.sid,
                        )
                    elif sinfo.moderator and socket_to_info[request.sid].moderator:
                        # Stop mods from being able to mute each other, only an admin can mute a mod.
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' cannot be muted."},
                            room=request.sid,
                        )
                    else:
                        # User has permission to mute, reply with the status.
                        changed = (sinfo.muted is False)
                        sinfo.muted = True

                        if changed:
                            socketio.emit(
                                'server',
                                {'msg': f"User '{message}' has been muted."},
                                room=request.sid,
                            )
                            socketio.emit(
                                'server',
                                {'msg': "You have been muted."},
                                room=sinfo.sid,
                            )
                        else:
                            socketio.emit(
                                'server',
                                {'msg': f"User '{message}' is already muted."},
                                room=request.sid,
                            )

                    # We found our guy, let's bail.
                    break
            else:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized user '{message}'"},
                    room=request.sid,
                )
        elif command in ["/unmute", "/unquiet"]:
            if not (socket_to_info[request.sid].admin or socket_to_info[request.sid].moderator):
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                    room=request.sid,
                )
                return

            message = message.strip().lower()
            for sinfo in socket_to_info.values():
                if sinfo.username.lower() == message and sinfo.streamer == socket_to_info[request.sid].streamer:
                    if sinfo.admin:
                        # This should never happen, but let's guard against it anyway.
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' cannot be unmuted."},
                            room=request.sid,
                        )
                    elif sinfo.moderator and socket_to_info[request.sid].moderator:
                        # Stop mods from being able to unmute each other, only an admin can unmute a mod.
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' cannot be unmuted."},
                            room=request.sid,
                        )
                    else:
                        # User has permission to unmute, reply with the status.
                        changed = (sinfo.muted is True)
                        sinfo.muted = False

                        if changed:
                            socketio.emit(
                                'server',
                                {'msg': f"User '{message}' has been unmuted."},
                                room=request.sid,
                            )
                            socketio.emit(
                                'server',
                                {'msg': "You have been unmuted."},
                                room=sinfo.sid,
                            )
                        else:
                            socketio.emit(
                                'server',
                                {'msg': f"User '{message}' is not muted."},
                                room=request.sid,
                            )

                    # We found our guy, let's bail.
                    break
            else:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized user '{message}'"},
                    room=request.sid,
                )
        elif command in ["/mod"]:
            if not socket_to_info[request.sid].admin:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                    room=request.sid,
                )
                return

            message = message.strip().lower()
            for sinfo in socket_to_info.values():
                if sinfo.username.lower() == message and sinfo.streamer == socket_to_info[request.sid].streamer:
                    if sinfo.admin:
                        # Admins shouldn't be able to set themselves or each other as mods.
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' cannot be promoted to moderator."},
                            room=request.sid,
                        )
                    else:
                        # We're good.
                        changed = (sinfo.moderator is False)
                        sinfo.moderator = True

                        if changed:
                            socketio.emit(
                                'server',
                                {'msg': f"User '{message}' has been promoted to moderator."},
                                room=request.sid,
                            )
                            socketio.emit(
                                'server',
                                {'msg': "You have been promoted to moderator."},
                                room=sinfo.sid,
                            )
                        else:
                            socketio.emit(
                                'server',
                                {'msg': f"User '{message}' is already a moderator."},
                                room=request.sid,
                            )

                    break
            else:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized user '{message}'"},
                    room=request.sid,
                )
        elif command in ["/demod", "/unmod"]:
            if not socket_to_info[request.sid].admin:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                    room=request.sid,
                )
                return

            message = message.strip().lower()
            for sinfo in socket_to_info.values():
                if sinfo.username.lower() == message and sinfo.streamer == socket_to_info[request.sid].streamer:
                    if sinfo.admin:
                        # Admins shouldn't be able to set themselves or each other as mods, so this should never
                        # happen. But, guard against it anyway.
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' cannot be demoted from moderator."},
                            room=request.sid,
                        )
                    else:
                        # We're good.
                        changed = (sinfo.moderator is True)
                        sinfo.moderator = False

                        if changed:
                            socketio.emit(
                                'server',
                                {'msg': f"User '{message}' has been demoted from moderator."},
                                room=request.sid,
                            )
                            socketio.emit(
                                'server',
                                {'msg': "You have been demoted from moderator."},
                                room=sinfo.sid,
                            )
                        else:
                            socketio.emit(
                                'server',
                                {'msg': f"User '{message}' is not a moderator."},
                                room=request.sid,
                            )

                    break
            else:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized user '{message}'"},
                    room=request.sid,
                )
        elif command in ["/rename"]:
            if not (socket_to_info[request.sid].admin or socket_to_info[request.sid].moderator):
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                    room=request.sid,
                )
                return

            message = message.strip()
            matcher = message.lower()
            for sinfo in socket_to_info.values():
                if matcher.startswith(sinfo.username.lower()) and sinfo.streamer == socket_to_info[request.sid].streamer:
                    new_name = message[len(sinfo.username.lower()):]
                    if bool(new_name) and new_name[0] != ' ':
                        # This was a partial match, skip it.
                        continue
                    new_name = new_name.strip()

                    if not new_name:
                        socketio.emit(
                            'server',
                            {'msg': f"Unspecified new username for user '{matcher}'"},
                            room=request.sid,
                        )
                    elif message_length(data, new_name) > 20:
                        socketio.emit(
                            'server',
                            {'msg': 'Too long of a name specified, try a different name.'},
                            room=request.sid,
                        )
                    else:
                        for user in users_in_room(socket_to_info[request.sid].streamer):
                            if user['username'].lower() == new_name.lower():
                                socketio.emit(
                                    'server',
                                    {'msg': 'Name has already been taken, try a different name.'},
                                    room=request.sid,
                                )
                                break
                        else:
                            old = sinfo.username
                            if sinfo.admin:
                                # Nobody with admin or mod powers should be able to rename an admin.
                                socketio.emit(
                                    'server',
                                    {'msg': f"User '{old.lower()}' cannot be renamed."},
                                    room=request.sid,
                                )
                            elif sinfo.moderator and socket_to_info[request.sid].moderator:
                                # Stop mods from being able to rename each other, only an admin can rename a mod.
                                socketio.emit(
                                    'server',
                                    {'msg': f"User '{old.lower()}' cannot be renamed."},
                                    room=request.sid,
                                )
                            else:
                                # User has permission to rename another user, let's execute it.
                                sinfo.username = new_name

                                insert_event(
                                    data,
                                    ChangeNameEvent(
                                        now(),
                                        socket_to_info[request.sid].streamer,
                                        old,
                                        new_name,
                                    )
                                )

                                socketio.emit(
                                    'rename',
                                    {
                                        'newname': new_name,
                                        'oldname': old,
                                        'type': sinfo.type,
                                        'color': sinfo.htmlcolor,
                                        'users': users_in_room(socket_to_info[request.sid].streamer),
                                    },
                                    room=socket_to_info[request.sid].streamer,
                                )

                    # We found our guy, let's bail.
                    break
            else:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized user '{message}'"},
                    room=request.sid,
                )
        elif command in ["/desc", "/description"]:
            if not socket_to_info[request.sid].admin:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                    room=request.sid,
                )
                return

            streamer = socket_to_info[request.sid].streamer
            description = emotes(message.strip())
            data.execute(
                "UPDATE streamersettings SET `description` = :description WHERE `username` = :streamer",
                {"streamer": streamer, "description": description}
            )

            socketio.emit(
                'server',
                {'msg': "Stream description updated!"},
                room=request.sid,
            )
        elif command in ["/password"]:
            if not socket_to_info[request.sid].admin:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                    room=request.sid,
                )
                return

            streamer = socket_to_info[request.sid].streamer
            if message:
                data.execute(
                    "UPDATE streamersettings SET `streampass` = :password WHERE `username` = :streamer",
                    {"streamer": streamer, "password": message}
                )
                socketio.emit(
                    'server',
                    {'msg': f"Stream password set to \"{message}\"!"},
                    room=request.sid,
                )
                socketio.emit(
                    'password set',
                    {
                        "password": message,
                    },
                    room=request.sid,
                )
                socketio.emit(
                    'password activated',
                    {
                        "username": streamer,
                    },
                    room=socket_to_info[request.sid].streamer,
                )
            else:
                data.execute(
                    "UPDATE streamersettings SET `streampass` = :password WHERE `username` = :streamer",
                    {"streamer": streamer, "password": None}
                )
                socketio.emit(
                    'server',
                    {'msg': "Stream password removed!"},
                    room=request.sid,
                )
                socketio.emit(
                    'password deactivated',
                    {
                        "username": streamer,
                        "msg": "Stream password has been removed.",
                    },
                    room=socket_to_info[request.sid].streamer,
                )
        else:
            socketio.emit(
                'server',
                {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                room=request.sid,
            )
            return
    else:
        if socket_to_info[request.sid].muted:
            socketio.emit(
                'server',
                {'msg': "You are muted!"},
                room=request.sid,
            )
        else:
            insert_event(
                data,
                SendMessageEvent(
                    now(),
                    socket_to_info[request.sid].streamer,
                    socket_to_info[request.sid].username,
                    emotes(message),
                )
            )

            socketio.emit(
                'message received',
                {
                    'username': socket_to_info[request.sid].username,
                    'type': socket_to_info[request.sid].type,
                    'color': socket_to_info[request.sid].htmlcolor,
                    'message': emotes(message),
                },
                room=socket_to_info[request.sid].streamer,
            )


@socketio.on('get color')  # type: ignore
def return_color(json: Dict[str, Any], methods: List[str] = ['GET', 'POST']) -> None:
    if request.sid not in socket_to_info:
        socketio.emit('error', {'msg': 'User is not authenticated?'}, room=request.sid)
        return

    socketio.emit(
        'return color',
        {'color': socket_to_info[request.sid].htmlcolor},
        room=request.sid,
    )


@socketio.on('drawing')  # type: ignore
def handle_drawing(json: Dict[str, Any], methods: List[str] = ['GET', 'POST']) -> None:
    if 'src' not in json:
        socketio.emit('error', {'msg': 'Image mssing from JSON?'}, room=request.sid)
        return

    if request.sid not in socket_to_info:
        socketio.emit('error', {'msg': 'User is not authenticated?'}, room=request.sid)
        return

    # Update user presence information
    update_presence(request.sid, socket_to_info[request.sid].streamer)

    src = json['src'].strip()

    # Verify that this is a valid picture with the right dimensions (stop arbitrary console-based
    # picture sending in most cases).
    try:
        header, data = src.split(",", 1)
        if not header.startswith("data:") or not header.endswith("base64"):
            raise ValueError("Invaid image header")

        with urllib.request.urlopen(src) as fp:
            img = Image.open(fp)
            width, height = img.size

            if width != PICTOCHAT_IMAGE_WIDTH or height != PICTOCHAT_IMAGE_HEIGHT:
                raise ValueError("Invalid image size")

        if socket_to_info[request.sid].muted:
            socketio.emit(
                'server',
                {'msg': "You are muted!"},
                room=request.sid,
            )
        else:
            insert_event(
                mysql(),
                SendDrawingEvent(
                    now(),
                    socket_to_info[request.sid].streamer,
                    socket_to_info[request.sid].username,
                    src,
                )
            )

            socketio.emit(
                'drawing received',
                {
                    'username': socket_to_info[request.sid].username,
                    'type': socket_to_info[request.sid].type,
                    'color': socket_to_info[request.sid].htmlcolor,
                    'src': src,
                },
                room=socket_to_info[request.sid].streamer,
            )
    except ValueError:
        socketio.emit(
            'server',
            {'msg': "Invalid drawing received!"},
            room=request.sid,
        )
