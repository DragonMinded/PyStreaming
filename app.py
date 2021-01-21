import argparse
import calendar
import datetime
import os
import yaml
from flask import Flask, Response, abort, jsonify, render_template, request, make_response
from flask_socketio import SocketIO, join_room  # type: ignore
from typing import Any, Dict, List, Optional
from werkzeug.middleware.proxy_fix import ProxyFix

from data import Data


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')
config: Dict[str, Any] = {}


def mysql() -> Data:
    global config
    return Data(config)


def now() -> int:
    """
    Returns the current unix timestamp in the UTC timezone.
    """
    return calendar.timegm(datetime.datetime.utcnow().timetuple())


def modified(fname: str) -> int:
    """
    Returns the modification time in the UTC timezone.
    """
    return calendar.timegm(datetime.datetime.utcfromtimestamp(os.path.getmtime(fname)).timetuple())


class SocketInfo:
    def __init__(self, sid: Any, ip: str, streamer: str, username: str, admin: bool, moderator: bool, muted: bool) -> None:
        self.sid = sid
        self.ip = ip
        self.streamer = streamer
        self.username = username
        self.admin = admin
        self.moderator = moderator
        self.muted = muted


class PresenceInfo:
    def __init__(self, sid: Any, streamer: str) -> None:
        self.sid = sid
        self.streamer = streamer
        self.timestamp = now()


socket_to_info: Dict[Any, SocketInfo] = {}
socket_to_presence: Dict[Any, PresenceInfo] = {}


def users_in_room(streamer: str) -> List[str]:
    return [i.username for i in socket_to_info.values() if i.streamer == streamer]


def stream_count(streamer: str) -> int:
    oldest = now() - 30
    return len([None for x in socket_to_presence.values() if x.streamer == streamer and x.timestamp >= oldest])


def stream_live(streamkey: str) -> bool:
    global config

    m3u8 = os.path.join(config['hls_dir'], streamkey) + '.m3u8'
    if not os.path.isfile(m3u8):
        # There isn't a playlist file, we aren't live.
        return False

    delta = now() - modified(m3u8)
    if delta >= int(config['hls_playlist_length']):
        return False

    return True


def fetch_m3u8(streamkey: str) -> Optional[str]:
    global config

    m3u8 = os.path.join(config['hls_dir'], streamkey) + '.m3u8'
    if not os.path.isfile(m3u8):
        # There isn't a playlist file, we aren't live.
        return None

    with open(m3u8, "rb") as bfp:
        return bfp.read().decode('utf-8')


def fetch_ts(filename: str) -> Optional[bytes]:
    global config

    ts = os.path.join(config['hls_dir'], filename)
    if not os.path.isfile(ts):
        # The file doesn't exist
        return None

    with open(ts, "rb") as bfp:
        return bfp.read()


def symlink(oldname: str, newname: str) -> None:
    src = os.path.join(config['hls_dir'], oldname)
    dst = os.path.join(config['hls_dir'], newname)
    try:
        os.symlink(src, dst)
    except FileExistsError:
        pass


@app.route('/')
def index() -> str:
    cursor = mysql().execute(
        "SELECT `username`, `key`, `description` FROM streamersettings",
    )
    streamers = [
        {
            'username': result['username'],
            'live': stream_live(result['key']), 'count': stream_count(result['username'].lower()),
            'description': result['description'] if result['description'] else '',
        }
        for result in cursor.fetchall()
    ]
    return render_template('index.html', streamers=streamers)


@app.route('/<streamer>/')
def stream(streamer: str) -> str:
    cursor = mysql().execute(
        "SELECT username FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        abort(404)

    result = cursor.fetchone()
    return render_template('stream.html', streamer=result["username"])


@app.route('/<streamer>/info')
def streaminfo(streamer: str) -> Response:
    streamer = streamer.lower()

    cursor = mysql().execute(
        "SELECT `username`, `key`, `description` FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        abort(404)

    result = cursor.fetchone()
    live = stream_live(result['key'])
    return jsonify({
        'live': live,
        'count': stream_count(streamer) if live else 0,
        'description': result['description'] if result['description'] else '',
    })


@app.route('/<streamer>/playlist.m3u8')
def streamplaylist(streamer: str) -> str:
    streamer = streamer.lower()

    cursor = mysql().execute(
        "SELECT `username`, `key` FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        abort(404)

    result = cursor.fetchone()
    key = result['key']

    if not stream_live(key):
        abort(404)

    m3u8 = fetch_m3u8(key)
    if m3u8 is None:
        abort(404)

    lines = m3u8.splitlines()
    for i in range(len(lines)):
        if lines[i].startswith(key) and lines[i][-3:] == ".ts":
            # We need to rewrite this
            oldname = lines[i]
            newname = f"{streamer}" + lines[i][len(key):]
            symlink(oldname, newname)
            lines[i] = "/hls/" + newname

    m3u8 = "\n".join(lines)
    return m3u8


@app.route('/hls/<filename>')
def streamts(filename: str) -> bytes:
    # This is a debugging endpoint only, your production nginx setup should handle this.
    ts = fetch_ts(filename)
    if ts is None:
        abort(404)

    response = make_response(ts)
    response.headers.set('Content-Type', 'video/mp2t')
    return response


@app.route('/auth/on_publish', methods=["GET", "POST"])
def publishcheck() -> Response:
    key = request.values.get('name')
    if key is None:
        # We don't have a stream key, deny it.
        abort(404)

    cursor = mysql().execute(
        "SELECT `key` FROM streamersettings WHERE `key` = :key",
        {"key": key},
    )
    if cursor.rowcount != 1:
        # We didn't find a registered streamer with this key, deny it.
        abort(404)

    # This is fine, allow it
    return "Stream ok!", 200


@socketio.on('connect')
def connect() -> None:
    if request.sid in socket_to_info:
        del socket_to_info[request.sid]


@socketio.on('disconnect')
def disconnect() -> None:
    if request.sid in socket_to_info:
        info = socket_to_info[request.sid]
        del socket_to_info[request.sid]

        socketio.emit('disconnected', {'username': info.username, 'users': users_in_room(info.streamer)}, room=info.streamer)
    if request.sid in socket_to_presence:
        del socket_to_presence[request.sid]


@socketio.on('presence')
def handle_presence(json, methods=['GET', 'POST']) -> None:
    if 'streamer' not in json:
        return

    # Update user presence information
    streamer = json['streamer'].lower()
    socket_to_presence[request.sid] = PresenceInfo(request.sid, streamer)


@socketio.on('login')
def handle_login(json, methods=['GET', 'POST']) -> None:
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

    streamer = json['streamer'].lower()
    username = json['username']
    key = json.get('key', None)

    # Update user presence information
    socket_to_presence[request.sid] = PresenceInfo(request.sid, streamer)

    cursor = mysql().execute(
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

    socket_to_info[request.sid] = SocketInfo(request.sid, str(request.remote_addr), streamer, json['username'], admin, False, False)
    join_room(streamer)
    socketio.emit('login success', {'username': json['username']}, room=request.sid)
    socketio.emit('connected', {'username': json['username'], 'users': users_in_room(streamer)}, room=streamer)

    if admin:
        socketio.emit('server', {'msg': 'You have admin rights.'}, room=request.sid)


@socketio.on('message')
def handle_message(json, methods=['GET', 'POST']) -> None:
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
    socket_to_presence[request.sid] = PresenceInfo(request.sid, socket_to_info[request.sid].streamer)

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
                socketio.emit(
                    'message received',
                    {
                        'username': socket_to_info[request.sid].username,
                        'message': message,
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
                socketio.emit(
                    'action received',
                    {
                        'username': socket_to_info[request.sid].username,
                        'message': message,
                    },
                    room=socket_to_info[request.sid].streamer,
                )
        elif command in ["/help"]:
            messages = [
                "The following commands are recognized:",
                "/help - show this message",
                "/users - show the currently chatting users",
                "/me - perform an action",
            ]
            if socket_to_info[request.sid].admin:
                messages.append("/description <text> - set the stream description")
                messages.append("/mod <user> - grant moderator privileges to user")
                messages.append("/demod <user> - revoke moderator privileges to user")
            if socket_to_info[request.sid].admin or socket_to_info[request.sid].moderator:
                messages.append("/mute <user> - mute user")
                messages.append("/unmute <user> - unmute user")

            for message in messages:
                socketio.emit(
                    'server',
                    {'msg': message},
                    room=request.sid,
                )
        elif command in ["/users"]:
            socketio.emit(
                'server',
                {'msg': 'Users in chat: ' + ", ".join(users_in_room(socket_to_info[request.sid].streamer))},
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
            for user in socket_to_info.values():
                if user.username.lower() == message and user.streamer == socket_to_info[request.sid].streamer:
                    changed = (user.muted is False)
                    user.muted = True

                    if changed:
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' has been muted."},
                            room=request.sid,
                        )
                        socketio.emit(
                            'server',
                            {'msg': "You have been muted."},
                            room=user.sid,
                        )
                    else:
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' is already muted."},
                            room=request.sid,
                        )
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
            for user in socket_to_info.values():
                if user.username.lower() == message and user.streamer == socket_to_info[request.sid].streamer:
                    changed = (user.muted is True)
                    user.muted = False

                    if changed:
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' has been unmuted."},
                            room=request.sid,
                        )
                        socketio.emit(
                            'server',
                            {'msg': "You have been unmuted."},
                            room=user.sid,
                        )
                    else:
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' is not muted."},
                            room=request.sid,
                        )
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
            for user in socket_to_info.values():
                if user.username.lower() == message and user.streamer == socket_to_info[request.sid].streamer:
                    changed = (user.moderator is False)
                    user.moderator = True

                    if changed:
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' has been promoted to moderator."},
                            room=request.sid,
                        )
                        socketio.emit(
                            'server',
                            {'msg': "You have been promoted to moderator."},
                            room=user.sid,
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
            for user in socket_to_info.values():
                if user.username.lower() == message and user.streamer == socket_to_info[request.sid].streamer:
                    changed = (user.moderator is True)
                    user.moderator = False

                    if changed:
                        socketio.emit(
                            'server',
                            {'msg': f"User '{message}' has been demoted from moderator."},
                            room=request.sid,
                        )
                        socketio.emit(
                            'server',
                            {'msg': "You have been demoted from moderator."},
                            room=user.sid,
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
        elif command in ["/desc", "/description"]:
            if not socket_to_info[request.sid].admin:
                socketio.emit(
                    'server',
                    {'msg': f"Unrecognized command '{command}', use '/help' for info."},
                    room=request.sid,
                )
                return

            streamer = socket_to_info[request.sid].streamer
            description = message.strip()
            mysql().execute(
                "UPDATE streamersettings SET `description` = :description WHERE `username` = :streamer",
                {"streamer": streamer, "description": description}
            )

            socketio.emit(
                'server',
                {'msg': "Stream description updated!"},
                room=request.sid,
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
            socketio.emit(
                'message received',
                {
                    'username': socket_to_info[request.sid].username,
                    'message': message,
                },
                room=socket_to_info[request.sid].streamer,
            )


def load_config(filename: str) -> None:
    global config

    config.update(yaml.safe_load(open(filename)))  # type: ignore
    config['database']['engine'] = Data.create_engine(config)
    app.secret_key = config['secret_key']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="A front end services provider for eAmusement games.")
    parser.add_argument("-p", "--port", help="Port to listen on. Defaults to 5678", type=int, default=5678)
    parser.add_argument("-d", "--debug", help="Enable debug mode. Defaults to off", action="store_true")
    parser.add_argument("-n", "--nginx-proxy", help="Number of nginx proxies in front of this server. Defaults to 0", type=int, default=0)
    parser.add_argument("-c", "--config", help="Config file to parse for instance settings. Defaults to config.yaml", type=str, default="config.yaml")
    args = parser.parse_args()

    load_config(args.config)

    if args.nginx_proxy > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_host=args.nginx_proxy, x_proto=args.nginx_proxy, x_for=args.nginx_proxy)
    socketio.run(app, host='0.0.0.0', port=args.port, debug=args.debug)
