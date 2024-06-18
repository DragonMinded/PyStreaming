import datetime
from flask import (
    Response,
    abort,
    jsonify,
    render_template,
    redirect,
    make_response,
    url_for,
)
from typing import Any, Dict, Optional
from werkzeug.datastructures import Authorization

from app import app, config, request
from data import Data
from events import (
    StartStreamingEvent,
    StopStreamingEvent,
    insert_event,
)
from presence import stream_count, users_in_room
from helpers import (
    PICTOCHAT_IMAGE_WIDTH,
    PICTOCHAT_IMAGE_HEIGHT,
    clean_symlinks,
    emotes,
    fetch_m3u8,
    fetch_ts,
    first_quality,
    get_emoji_unicode_dict,
    get_aliases_unicode_dict,
    mysql,
    now,
    stream_live,
    symlink,
)


# Allow cache-busting of entire frontend for stream page and chat updates.
FRONTEND_CACHE_BUST: str = "site.1.0.6"


@app.context_processor
def provide_globals() -> Dict[str, Any]:
    return {
        "cache_bust": f"v={FRONTEND_CACHE_BUST}",
    }


@app.route('/')
def index() -> str:
    cursor = mysql().execute(
        "SELECT `username`, `key`, `description`, `streampass` FROM streamersettings",
    )
    streamers = [
        {
            'username': result['username'],
            'live': stream_live(result['key'], first_quality()), 'count': stream_count(result['username'].lower()),
            'description': emotes(result['description']) if result['description'] else '',
            'locked': result['streampass'] is not None,
        }
        for result in cursor
    ]
    return render_template('index.html', streamers=streamers)


@app.route('/<streamer>/')
def stream(streamer: str) -> Response:
    data = mysql()
    cursor = data.execute(
        "SELECT username, streampass FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        abort(404)

    result = cursor.fetchone()

    streampass = result['streampass']
    if streampass is not None and request.cookies.get('streampass') != streampass:
        # This stream is password protected!
        return make_response(
            render_template(
                'password.html',
                streamer=result["username"],
            ),
            403
        )

    # The stream is either not password protected, or the user has already authenticated.
    qualities = config.get('video_qualities', None)
    if not qualities:
        playlists = [{"src": url_for('streamplaylist', streamer=streamer), "label": "live", "type": "application/x-mpegURL"}]
    else:
        playlists = [{"src": url_for('streamplaylistwithquality', streamer=streamer, quality=quality), "label": quality, "type": "application/x-mpegURL"} for quality in qualities]

    emojis = {
        **get_emoji_unicode_dict('en'),
        **get_aliases_unicode_dict(),
    }
    emojis = {key: emojis[key] for key in emojis if "__" not in key}

    cursor = data.execute(
        "SELECT alias, uri FROM emotes ORDER BY alias",
    )
    emotes = {f":{result['alias']}:": result['uri'] for result in cursor}
    icons = {
        'admin': url_for('static', filename='admin.png'),
        'moderator': url_for('static', filename='moderator.png'),
    }

    return make_response(
        render_template(
            'stream.html',
            streamer=result["username"],
            playlists=playlists,
            emojis=emojis,
            emotes=emotes,
            icons=icons,
            pictochat_image_width=PICTOCHAT_IMAGE_WIDTH,
            pictochat_image_height=PICTOCHAT_IMAGE_HEIGHT,
        )
    )


@app.route('/<streamer>/password', methods=["POST"])
def password(streamer: str) -> Response:
    streamer = streamer.lower()
    cursor = mysql().execute(
        "SELECT `username`, `streampass` FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        abort(404)

    # Verify the password.
    result = cursor.fetchone()
    streampass = result['streampass']
    if request.form.get('streampass') == streampass:
        expire_date = datetime.datetime.now()
        expire_date = expire_date + datetime.timedelta(days=1)
        response = make_response(redirect(url_for("stream", streamer=result["username"])))
        response.set_cookie("streampass", streampass, expires=expire_date)
        return response

    # Wrong password bucko!
    return make_response(
        render_template(
            'password.html',
            streamer=result["username"],
            password_invalid=True,
        ),
        403
    )


@app.route('/<streamer>/info')
def streaminfo(streamer: str) -> Response:
    streamer = streamer.lower()

    cursor = mysql().execute(
        "SELECT `username`, `streampass`, `key`, `description` FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        abort(404)

    # Doesn't cost us much, so let's clean up on the fly.
    clean_symlinks()

    result = cursor.fetchone()

    # First, verify they're even allowed to see this stream.
    streampass = result['streampass']
    if streampass is not None and request.cookies.get('streampass') != streampass:
        # This stream is password protected!
        abort(403)

    # The stream is either not password protected, or the user has already authenticated.
    live = stream_live(result['key'], first_quality())
    return make_response(jsonify({
        'live': live,
        'count': stream_count(streamer) if live else 0,
        'description': emotes(result['description']) if result['description'] else '',
    }))


@app.route('/<streamer>/playlist.m3u8')
def streamplaylist(streamer: str) -> str:
    streamer = streamer.lower()

    cursor = mysql().execute(
        "SELECT `username`, `streampass`, `key` FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        abort(404)

    result = cursor.fetchone()

    # First ensure they're even allowed to see this stream.
    streampass = result['streampass']
    if streampass is not None and request.cookies.get('streampass') != streampass:
        # This stream is password protected!
        abort(403)

    # The stream is either not password protected, or the user has already authenticated.
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
        if key in lines[i]:
            raise Exception("Possible stream key leak!")

    # Doesn't cost us much, so let's clean up on the fly.
    clean_symlinks()

    m3u8 = "\n".join(lines)
    return m3u8


@app.route('/<streamer>/playlist/<quality>.m3u8')
def streamplaylistwithquality(streamer: str, quality: str) -> str:
    streamer = streamer.lower()

    cursor = mysql().execute(
        "SELECT `username`, `streampass`, `key` FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        abort(404)

    result = cursor.fetchone()

    # First ensure they're even allowed to see this stream.
    streampass = result['streampass']
    if streampass is not None and request.cookies.get('streampass') != streampass:
        # This stream is password protected!
        abort(403)

    # The stream is either not password protected, or the user has already authenticated.
    key = result['key']

    if not stream_live(key, quality):
        abort(404)

    m3u8 = fetch_m3u8(key, quality)
    if m3u8 is None:
        abort(404)

    lines = m3u8.splitlines()
    for i in range(len(lines)):
        if lines[i].startswith(key + '_' + quality) and lines[i][-3:] == ".ts":
            # We need to rewrite this
            oldname = lines[i]
            newname = f"{streamer}_{quality}" + lines[i][(len(key) + len(quality) + 1):]
            symlink(oldname, newname)
            lines[i] = "/hls/" + newname
        if key in lines[i]:
            raise Exception("Possible stream key leak!")

    # Doesn't cost us much, so let's clean up on the fly.
    clean_symlinks()

    m3u8 = "\n".join(lines)
    return m3u8


@app.route('/hls/<filename>')
def streamts(filename: str) -> Response:
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

    data = mysql()
    cursor = data.execute(
        "SELECT `username`, `description`, `streampass` FROM streamersettings WHERE `key` = :key",
        {"key": key},
    )
    if cursor.rowcount != 1:
        # We didn't find a registered streamer with this key, deny it.
        abort(404)

    # Log that we started streaming.
    result = cursor.fetchone()
    insert_event(
        data,
        StartStreamingEvent(
            now(),
            result["username"].lower(),
            result["description"],
            result["streampass"],
        )
    )

    # This is fine, allow it
    return make_response("Stream ok!", 200)


@app.route('/auth/on_publish_done', methods=["GET", "POST"])
def donepublishcheck() -> Response:
    key = request.values.get('name')
    if key is None:
        # We don't have a stream key, can't link to an event.
        return make_response("Stream ok!", 200)

    data = mysql()
    cursor = data.execute(
        "SELECT `username` FROM streamersettings WHERE `key` = :key",
        {"key": key},
    )
    if cursor.rowcount != 1:
        # We didn't find a registered streamer with this key, can't link to an event.
        return make_response("Stream ok!", 200)

    # Log that we stopped streaming.
    result = cursor.fetchone()
    insert_event(
        data,
        StopStreamingEvent(
            now(),
            result["username"].lower(),
        )
    )
    return make_response("Stream ok!", 200)


def get_auth(data: Data, auth: Optional[Authorization]) -> Optional[str]:
    if not auth:
        return None

    if auth.type != "basic":
        return None

    if not auth.username or not auth.password:
        return None

    cursor = data.execute(
        "SELECT `username`, `key` FROM streamersettings WHERE username = :username",
        {"username": auth.username},
    )
    if cursor.rowcount != 1:
        return None

    result = cursor.fetchone()
    if auth.password == result["key"]:
        return auth.username.lower()

    return None


def __info(data: Data, streamer: str) -> Response:
    cursor = data.execute(
        "SELECT `username`, `key`, `streampass`, `description` FROM streamersettings WHERE username = :username",
        {"username": streamer},
    )
    if cursor.rowcount != 1:
        # Shouldn't happen due to auth check, but let's be sure.
        abort(404)

    result = cursor.fetchone()

    # First, verify they're even allowed to see this stream.
    streampass = result['streampass'] or None
    username = result['username']
    description = result['description'] or ''

    # Figure out if the stream itself is live.
    live = stream_live(result['key'], first_quality())

    # Grab viewer count, active chatters.
    users = [u["username"] for u in users_in_room(streamer)]
    viewers = stream_count(streamer) if live else 0

    # Return all that info!
    return make_response(jsonify({
        'username': username,
        'description': emotes(description),
        'streampass': streampass,
        'live': live,
        'viewers': viewers,
        'members': users,
    }))


@app.route('/api/info', methods=["GET"])
def fetchinfo() -> Response:
    data = mysql()
    streamer = get_auth(data, request.authorization)
    if not streamer:
        abort(401)

    return __info(data, streamer)


@app.route('/api/info', methods=["PATCH"])
def updateinfo() -> Response:
    data = mysql()
    streamer = get_auth(data, request.authorization)
    if not streamer:
        abort(401)

    content = request.json
    if isinstance(content, dict):
        if 'description' in content:
            data.execute(
                "UPDATE streamersettings SET description = :description WHERE username = :username LIMIT 1",
                {"username": streamer, "description": str(content["description"] or "")},
            )
        if 'streampass' in content:
            password = content["streampass"]
            if not password:
                password = None
            data.execute(
                "UPDATE streamersettings SET streampass = :password WHERE username = :username LIMIT 1",
                {'username': streamer, 'password': password},
            )

    return __info(data, streamer)


@app.route('/api/messages', methods=["POST"])
def sendmessage() -> Response:
    data = mysql()
    streamer = get_auth(data, request.authorization)
    if not streamer:
        abort(401)

    content = request.json
    if isinstance(content, dict):
        messagetype: Optional[str] = None
        message: Optional[str] = None

        if "type" in content:
            messagetype = str(content["type"])
        if not messagetype:
            messagetype = "normal"
        if "message" in content:
            message = str(content["message"])

        if messagetype is None or message is None:
            abort(400)
        if messagetype not in {"normal", "action", "server"}:
            abort(400)

        data.execute(
            "INSERT INTO pendingmessages (`username`, `type`, `message`) VALUES (:username, :type, :message)",
            {'username': streamer, 'type': messagetype, 'message': message},
        )

    return make_response(jsonify({}))
