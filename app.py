import argparse
import yaml
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room  # type: ignore
from typing import Any, Dict, List

from data import Data


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')
config: Dict[str, Any] = {}


class SocketInfo:
    def __init__(self, streamer: str, username: str) -> None:
        self.streamer = streamer
        self.username = username


socket_to_info: Dict[Any, SocketInfo] = {}


def users_in_room(streamer: str) -> List[str]:
    return [i.username for i in socket_to_info.values() if i.streamer == streamer]


@app.route('/')
def index() -> str:
    return render_template('index.html')


@app.route('/<streamer>/')
def stream(streamer: str) -> str:
    # TODO: Look up canonical name based on streamer here
    return render_template('stream.html', streamer=streamer)


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

    # TODO: Check streamer against a DB here
    streamer = json['streamer'].lower()

    for _, existing in socket_to_info.items():
        if existing.streamer != streamer:
            # Not the right room
            continue

        if existing.username.lower() == json['username'].lower():
            socketio.emit('error', {'msg': 'Username is taken'}, room=request.sid)
            return

    socket_to_info[request.sid] = SocketInfo(streamer, json['username'])
    join_room(streamer)
    socketio.emit('login success', {}, room=request.sid)
    socketio.emit('connected', {'username': json['username'], 'users': users_in_room(streamer)}, room=streamer)


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

    socketio.emit(
        'message received',
        {
            'username': socket_to_info[request.sid].username,
            'message': json['message'],
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
    parser.add_argument("-c", "--config", help="Config file to parse for instance settings. Defaults to config.yaml", type=str, default="config.yaml")
    args = parser.parse_args()

    load_config(args.config)

    socketio.run(app, host='0.0.0.0', port=args.port, debug=args.debug)
