from flask import (
    Flask,
    Request,
    request as base_request,
)
from flask_socketio import SocketIO  # type: ignore
from flask_cors import CORS  # type: ignore
from typing import Any, Dict, cast


app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*')
config: Dict[str, Any] = {}


# A quick hack to teach mypy about the valid SID parameter.
class StreamingRequest(Request):
    sid: Any


request: StreamingRequest = cast(StreamingRequest, base_request)
