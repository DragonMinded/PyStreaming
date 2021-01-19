from flask import Flask, render_template, request
from flask_socketio import SocketIO

from typing import Any, Dict


app = Flask(__name__)
app.config['SECRET_KEY'] = 'TODO:thisneedstochange'
socketio = SocketIO(app)


socket_to_username: Dict[Any, str] = {}


@app.route('/')
def html():
    return render_template('index.html')


@socketio.on('connect')
def connect():
    if request.sid in socket_to_username:
        del socket_to_username[request.sid]


@socketio.on('disconnect')
def disconnect():
    if request.sid in socket_to_username:
        username = socket_to_username[request.sid]
        del socket_to_username[request.sid]
        socketio.emit('disconnected', {'username': username, 'users': list(socket_to_username.values())})


@socketio.on('login')
def handle_login(json, methods=['GET', 'POST']):
    if request.sid in socket_to_username:
        socketio.emit('error', {'msg': 'SID already taken?'}, room=request.sid);
        return

    if 'username' not in json:
        socketio.emit('error', {'msg': 'Username mssing from JSON?'}, room=request.sid);
        return

    if len(json['username']) == 0:
        socketio.emit('error', {'msg': 'Username cannot be blank'}, room=request.sid);
        return

    for _, existing in socket_to_username.items():
        if existing.lower() == json['username'].lower():
            socketio.emit('error', {'msg': 'Username is taken'}, room=request.sid);
            return

    socket_to_username[request.sid] = json['username']
    socketio.emit('login success', {}, room=request.sid)
    socketio.emit('connected', {'username': json['username'], 'users': list(socket_to_username.values())})


@socketio.on('message')
def handle_message(json, methods=['GET', 'POST']):
    if 'message' not in json:
        socketio.emit('error', {'msg': 'Message mssing from JSON?'}, room=request.sid);
        return

    if len(json['message']) == 0:
        socketio.emit('warning', {'msg': 'Message cannot be blank'}, room=request.sid);
        return

    if request.sid not in socket_to_username:
        socketio.emit('error', {'msg': 'User is not authenticated?'}, room=request.sid);
        return

    socketio.emit('message received', {
        'username': socket_to_username[request.sid],
        'message': json['message'],
    })


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5678, debug=True)
