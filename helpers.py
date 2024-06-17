import calendar
import datetime
import emoji
import os
import random
import webcolors  # type: ignore
from typing import Any, Dict, Optional

from app import config
from data import Data


# Pictochat width/height, shared in a couple places.
PICTOCHAT_IMAGE_WIDTH: int = 230
PICTOCHAT_IMAGE_HEIGHT: int = 120


def mysql() -> Data:
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


def first_quality() -> Optional[str]:
    """
    Looks up all of the video qualities, and returns the first one listed. If none are listed
    in the config that is present, returns None.
    """

    qualities = config.get('video_qualities', None)
    if not qualities:
        return None
    firstq = qualities[0]
    if isinstance(firstq, str):
        return firstq
    return None


def stream_live(streamkey: str, quality: Optional[str] = None) -> bool:
    """
    Looks up a stream by the stream key and quality, returning True if the stream was last published to
    within the configured indicator delay, and False otherwise.
    """

    if quality:
        filename = f"{streamkey}_{quality}.m3u8"
    else:
        filename = streamkey + '.m3u8'
    m3u8 = os.path.join(config['hls_dir'], filename)
    if not os.path.isfile(m3u8):
        # There isn't a playlist file, we aren't live.
        return False

    delta = now() - modified(m3u8)
    if delta >= int(config.get('live_indicator_delay', 5)):
        return False

    return True


def get_color(color: str) -> Optional[int]:
    """
    Given either a hex color (in HTML style) or a CSS3 color name, attempts to return the actual RGB
    color that that color string represents.
    """

    color = color.strip().lower()

    if color == "random":
        # Pick a random webcolor.
        choices = [k for k in webcolors.CSS3_NAMES_TO_HEX]
        color = random.choice(choices)

    # Attempt to convert from any color specification to hex.
    try:
        color = webcolors.name_to_hex(color, spec=webcolors.CSS3)
    except ValueError:
        pass
    try:
        color = webcolors.normalize_hex(color)
    except ValueError:
        pass

    if len(color) != 7 or color[0] != '#':
        return None

    intval = int(color[1:], 16)
    if intval < 0 or intval > 0xFFFFFF:
        return None

    return intval


def fetch_m3u8(streamkey: str, quality: Optional[str] = None) -> Optional[str]:
    """
    Given a stream key and an optional quality, fetches the M3U8 contents corresponding to
    those details. If the streamer isn't live, this returns None instead.
    """

    if quality:
        filename = f"{streamkey}_{quality}"
    else:
        filename = streamkey
    m3u8 = os.path.join(config['hls_dir'], filename) + '.m3u8'
    if not os.path.isfile(m3u8):
        # There isn't a playlist file, we aren't live.
        return None

    with open(m3u8, "rb") as bfp:
        return bfp.read().decode('utf-8')


def fetch_ts(filename: str) -> Optional[bytes]:
    """
    Given a ts filename, grabs the data for that file. This is a debug function only, normally
    you would have your nginx proxy serve ts files directly.
    """

    ts = os.path.join(config['hls_dir'], filename)
    if not os.path.isfile(ts):
        # The file doesn't exist
        return None

    with open(ts, "rb") as bfp:
        return bfp.read()


def symlink(oldname: str, newname: str) -> None:
    """
    Given an old and a new name, perform a symlink from the old to the new name. Note that this
    assumes the old and new names are inside the configured hls directory.
    """

    src = os.path.join(config['hls_dir'], oldname)
    dst = os.path.join(config['hls_dir'], newname)
    try:
        os.symlink(src, dst)
    except FileExistsError:
        pass


def clean_symlinks() -> None:
    """
    Removes any previously created symlinks that no longer point at a valid file. This happens when
    the stream advances past an older file name and the file is deleted, leaving the symlink dangling.
    """

    try:
        for name in os.listdir(config['hls_dir']):
            if name not in (os.curdir, os.pardir):
                full = os.path.join(config['hls_dir'], name)
                if os.path.islink(full):
                    real = os.readlink(full)
                    if not os.path.isfile(real):
                        # This symlink points at an old file that nginx has removed.
                        # So, let's clean up!
                        os.remove(full)
    except Exception:
        # We don't want to interrupt playlist fetching due to a failure to
        # clean. If this happens the stream will pause.
        pass


_EMOJI_UNICODE: Dict[str, Any] = {lang: None for lang in emoji.LANGUAGES}  # Cache for the language dicts
_ALIASES_UNICODE: Dict[str, str] = {}  # Cache for the aliases dict


def get_emoji_unicode_dict(lang: str) -> Dict[str, Any]:
    """
    Generate dict containing all fully-qualified and component emoji name for a language
    The dict is only generated once per language and then cached in _EMOJI_UNICODE[lang]
    """

    if _EMOJI_UNICODE[lang] is None:
        _EMOJI_UNICODE[lang] = {data[lang]: emj for emj, data in emoji.EMOJI_DATA.items()
                                if lang in data and data['status'] <= emoji.STATUS['fully_qualified']}

    return _EMOJI_UNICODE[lang]  # type: ignore


def get_aliases_unicode_dict() -> Dict[str, str]:
    """
    Generate dict containing all fully-qualified and component aliases
    The dict is only generated once and then cached in _ALIASES_UNICODE
    """

    if not _ALIASES_UNICODE:
        _ALIASES_UNICODE.update(get_emoji_unicode_dict('en'))
        for emj, data in emoji.EMOJI_DATA.items():
            if 'alias' in data and data['status'] <= emoji.STATUS['fully_qualified']:
                for alias in data['alias']:
                    _ALIASES_UNICODE[alias] = emj

    return _ALIASES_UNICODE


def emotes(msg: str) -> str:
    return emoji.emojize(emoji.emojize(msg, language="alias"), language="en")


def message_length(data: Data, msg: str) -> int:
    # First, easy conversions.
    msg = emotes(msg)

    # Now, look up configured emoji aliases.
    cursor = data.execute(
        "SELECT alias FROM emotes ORDER BY alias",
    )
    for result in cursor:
        msg = msg.replace(f":{result['alias']}:", "*")

    # Now, return the length, where each emoji and emote counts as one character.
    return len(msg)
