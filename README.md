A simple web frontend that works in tandem with nginx-rtmp-module to provide a
streaming web site. A compatible RTMP video streaming source such as OBS can
send video and audio to an RTMP endpoint served by nginx and the stream will
show up for clients on a web page with included stream chat. There are simple
moderation commands such as mute available, live presence indication and a
layer that ensures stream keys are never exposed publicly.

# Future Enhancements

 * Kick and ban fron chat feature based on client IP.
 * Persistent username/account feature.
 * Emote and emoji support in chat.
 * Word filtering support for chat.
 * Rate limiting for message sends in chat.
 * Stream description/current action being streamed.
