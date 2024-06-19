A simple web frontend that works in tandem with nginx-rtmp-module to provide a
streaming web site. A compatible RTMP video streaming source such as OBS can
send video and audio to an RTMP endpoint served by nginx and the stream will
show up for clients on a web page with included stream chat. There are simple
moderation commands such as mute and rename available, live presence indication
and a layer that ensures stream keys are never exposed publicly. Streams can be
password-protected against arbitrary viewership. The stream chat allows for cusom
emoji to be added as well as simple pictochat-style drawings to be submitted.

# Setup

## Dependencies

This project assumes Python 3.6 or higher, due to (partial) use of type-hints.
It assumes a version of nginx with nginx-rtmp-module compiled and available.
It assumes a local, modern MySQL instance that you have permission to create
databases on. It assumes a linux-like environment to run all of these programs.

Project dependencies are in the `requirements.txt` file. To install these, run
the following command, preferrably in a
[virtual environment](https://docs.python.org/3.6/tutorial/venv.html) so as to
not pollute your system python installation:

```
python3 -m pip install -r requirements.txt
```

## Initial Setup

Once you have dependencies set up and operational and you have installed the
project dependencies into your virtual environment, its time to configure.
Edit (or rename) `config.yaml` and update the database section to point at
your MySQL instance. Make sure that you create a database and user that match
the settings in your `config.yaml` file. If you don't know how to do this, see
[this tutorial](https://matomo.org/faq/how-to-install/faq_23484/).

Once your database is set up, run the following command to hydrate the database:

```
python3 manage.py --config config.yaml database create
```

If you've renamed your `config.yaml` file, substitute that new name in the above
command. When this is done, you should have the table structure required to stream.
You do not have any authorized streamers, however. To add a streamer whose username
is "test" and whose stream key is "secretkey", run the following command:

```
python3 manage.py --config config.yaml streamer add --user test --key secretkey
```

You can substitute for your own username and secret key here. Again, if you renamed
your `config.yaml` file, substitute that new name in the above command.

## Management

The `manage.py` script is where you will do all of your database management. Run
the script with `--help` to see available commands. In the streamer sub-command
you can add streamers, remove them, list them, modify streamer parameters such as
stream password, streamer key and stream description. In the database sub-command
you can upgrade the database on a new version of this code and generate migration
scripts if you have modified the database schema and wish to make a pull request.
In the emoji sub-command you can add new custom emoji, remove existing ones and list
the custom emoji available. Make sure that you always give it the `config.yaml`
that you have customized in order to operate on the correct database.

## Running

You can start the server using the following command:

```
python3 pystreaming.py --config config.yaml --port 12345
```

This will run the application in production mode. If you want to run the
application with more logging and auto-reloading on file changes, add `--debug`
to the arguments. Remember that you can run the above script with `--help` to
see options. Once this is up and running, you can visit the web page at
[http://127.0.0.1:12345/](http://127.0.0.1:12345/). If you are setting this up
on a remote server, substitute the server's public IP for `127.0.0.1` above.
If you have changed the port in the above command, make sure you change the port
in the URL as well. You should see a list of all the streamers you've added
using the `manage.py` script. You can click on any of them to go to their
streamer page.

## nginx Configuration

We will use nginx as the RTMP listening server and HLS transcoder which powers
the media portion of this setup. First, you will want to edit your `nginx.conf`
to include a section similar to the following:

```
rtmp {
    server {
        # Standard RTMP port, where OBS expects to send data.
        listen 1935;

        # Stream chunk size, leave as-is.
        chunk_size 4096;

        # Allow publishing from any IP. We will use the "on_publish" hook for security.
        allow publish all;

        # Deny playback from any IP. This means RTMP clients like VLC cannot connect
        # directly to the server to watch streams.
        deny play all;

        # URL nginx will check when a user tries to stream, to verify the stream key
        # is correct. You should leave this as 127.0.0.1 because nginx should only
        # look on the local host for the auth endpoint.
        on_publish http://127.0.0.1:12345/auth/on_publish;
        on_publish_done http://127.0.0.1:12345/auth/on_publish_done;

        # Create the "/live" endpoint people can stream to.
        application live {
            # Enable this endpoint.
            live on;

            # Disable recording to flv files.
            record off;

            # Enable HLS transcoding. RTMP clients in the browser no longer exist.
            hls on;

            # Where we will put the HLS files and playlists.
            hls_path /path/to/hls/;

            # How long each segment should be. If you are experiencing large stream
            # delays, you can reduce this down to 1s.
            hls_fragment 3s;

            # How much playback buffer we keep around. If this is too short, there
            # will be no live replay buffer available in the video player. Should
            # be a multiple of the hls_fragment length above.
            hls_playlist_length 30s;
        }
    }
}
```

There are a few things you will want to customize in that above section based on
your setup. First is the port in the `on_publish` section. The port must match the
port you run your application with. If you changed your `--port` setting when you
ran `pystreaming.py`, make sure to also change the port in `on_publish` so that nginx
can validate streamer permissions. The path given in `hls_path` should be readable
and writeable by the nginx user and the python server user, and should match the
path in your `config.yaml` `hls_dir` setting. nginx will put transcoded HLS files
in this directory and this is where the python application will look to find stream
information.

If you've set everything up correctly and are running `pystreaming.py` as well as nginx,
you should be able to point OBS at `rtmp://127.0.0.1/live` and start streaming.
Make sure your stream key matches what you added using `manage.py` above! If you
are setting this up on a remote server, substitute the server's public IP for
`127.0.0.1` in the URL above. If everything is set up right, you should see the
stream go live on the web interface.

### Transcoding Multiple Qualities

By default, the above setup will deliver a single quality stream to all viewers
that is based on your source configuration (most-likely in OBS or another streaming
software). If you want to provide multiple quality streams for viewers with slower
internet connections you will need to modify your `nginx.conf` as well as your
`config.yaml` setup. In this alternate configuration you will use ffmpeg to
translate the incoming stream to multiple streams on the fly. First you will want
to edit your `nginx.conf` to include a section similar to the following (instead of
the above simpler config):

```
rtmp {
    server {
        # Standard RTMP port, where OBS expects to send data.
        listen 1935;

        # Stream chunk size, leave as-is.
        chunk_size 4096;

        # Create the "/live" endpoint people can stream to.
        application live {
            # Allow publishing from any IP. We will use the "on_publish" hook for security.
            allow publish all;

            # Allow localhost to play this stream back over RTML. This is important as this is
            # how ffmpeg will transcode the stream.
            allow play 127.0.0.1;

            # Enable this endpoint.
            live on;

            # Disable recording to flv files.
            record off;

            # URL nginx will check when a user tries to stream, to verify the stream key
            # is correct. You should leave this as 127.0.0.1 because nginx should only
            # look on the local host for the auth endpoint.
            on_publish http://127.0.0.1:12345/auth/on_publish;
            on_publish_done http://127.0.0.1:12345/auth/on_publish_done;

            # Push transcoded streams to the "/hls" endpoint. Feel free to change the
            # parameters of the various transcoded streams, add or drop them at will.
            # If you don't wish to include the original quality stream you can drop the
            # line which copies video/audio to the "/hls" endpoint.
            exec ffmpeg -i rtmp://127.0.0.1:1935/$app/$name
            -c copy -f flv rtmp://127.0.0.1:1935/hls/$name_Original
            -c:v libx264 -acodec copy -b:v 2304k -vf "scale=1080:trunc(ow/a/2)*2" -tune zerolatency -preset veryfast -crf 23 -g 60 -hls_list_size 0 -f flv rtmp://127.0.0.1:1935/hls/$name_1080P
            -c:v libx264 -acodec copy -b:v 768k -vf "scale=720:trunc(ow/a/2)*2" -tune zerolatency -preset veryfast -crf 23 -g 60 -hls_list_size 0 -f flv rtmp://127.0.0.1:1935/hls/$name_720P
            -c:v libx264 -acodec copy -b:v 256k -vf "scale=480:trunc(ow/a/2)*2" -tune zerolatency -preset veryfast -crf 23 -g 60 -hls_list_size 0 -f flv rtmp://127.0.0.1:1935/hls/$name_480P;
        }

        # Create the "/hls" endpoint used by ffmpeg to push transcoded streams.
        application hls {
            # Only allow publishing from localhost, specifically from ffmpeg from above.
            allow publish 127.0.0.1;

            # Deny playback from any IP. This means RTMP clients like VLC cannot connect
            # directly to the server to watch streams.
            deny play all;

            # Enable this endpoint.
            live on;

            # Disable recording to flv files.
            record off;

            # Enable HLS transcoding. RTMP clients in the browser no longer exist.
            hls on;

            # Where we will put the HLS files and playlists.
            hls_path /path/to/hls/;

            # How long each segment should be. If you are experiencing large stream
            # delays, you can reduce this down to 1s.
            hls_fragment 3s;

            # How much playback buffer we keep around. If this is too short, there
            # will be no live replay buffer available in the video player. Should
            # be a multiple of the hls_fragment length above.
            hls_playlist_length 30s;
        }
    }
}
```

You'll notice that compared to the simpler setup, we split the RTMP server into
two pieces. The first piece handles authentication based on stream key and is the
endpoint you will stream to. Its responsible for launching ffmpeg to transcode streams.
The second piece listens for the transcoded streams and is responsible for writing out
the HLS file fragments that make the whole thing work. In both the simpler and more
complex setup, you will be pointing your streaming setup at the `/live` RTMP endpoint.

In order for this to work with the streaming frontend you also need to edit your
`config.yaml` to specify the qualities you support. Without this, it will assume no
suffix for stream keys and will only work with the simpler `nginx.conf`. For the demo
`nginx.conf` laid out just above, you will want a similar section in your `config.yaml`
that looks like the following:

```
video_qualities:
    - Original
    - 1080P
    - 720P
    - 480P
```

Notice that the suffixes we provided after `$name` for the original and transcoded streams
are all listed here. When you set the software up in this manner, a configuration gear will
be visible on the stream for viewers where they can choose a quality. You'll want to verify
with a test stream to ensure that your streaming server can handle the load of transcoding.
If it can't, you'll notice that all qualities will buffer randomly and your CPU usage will
be too high for the number of cores. If your server can't keep up, choose fewer transcodes
and try again.

## Running Behind nginx

Its a good idea to serve up the web interface behind nginx instead of directly.
This allows you to set up things such as SSL, provide the weight of nginx to deliver
HLS files to clients and generally makes your setup more robust. First, add a
site to `sites-available` with contents similar to the following:

```
server {
    # The domain name this nginx config serves.
    server_name coolstreamingsite.com;

    # Listen on port 80 (standard web port).
    listen 80;

    # Don't advertise nginx.
    server_tokens off;

    # Set up the root to point at our server.
    location / {
        # Make sure to pass on IP information.
        include proxy_params;

        # Pass traffic to pystreaming.py.
        proxy_pass http://127.0.0.1:12345/;
    }

    # Set up websockets for stream chat.
    location /socket.io {
        # Leave all of this as-is.
        include proxy_params;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";

        # Pass websockets to pystreaming.py
        proxy_pass http://127.0.0.1:12345/socket.io;
    }

    # Set up HLS directory so nginx can directly handle stream chunks.
    location /hls {
        # Leave all of this as-is.
        add_header Cache-Control no-cache;
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Expose-Headers' 'Content-Length';

        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain charset=UTF-8';
            add_header 'Content-Length' 0;
            return 204;
        }

        types {
            application/vnd.apple.mpegurl m3u8;
            video/mp2t ts;
        }

        # The root directory which holds the "hls" subdirectory we are putting
        # HLS files in. The full directory will be this root and the location
        # concatenated. In this case "/path/to/hls"
        root /path/to;

        # Don't allow listing of the directory, to keep stream keys secret.
        autoindex off;
    }

    location /static {
        # Make sure to update this to the directory you're running pystreaming.py out
        # of as it allows nginx to handle static resources, taking strain off
        # of the python application.
        root /location/of/this/repo;

        # No need to show the world our dirty laundry.
        autoindex off;
    }
}
```

There are a few things you wil want to modify in this file. For starters, if you
aren't using DNS, get rid of the `server_name` entry. If you are, make
sure this setting matches your domain name. Next, its important that the port in
both `proxy_pass` settings matches the port you ran your `pystreaming.py` script with.
This should match the port in your `nginx.conf` as well. Finally, make sure the
directory you chose to put HLS files in matches the `root` option. nginx is a bit
weird here, since `/hls` is a subdirectory, you give it the parent of the option
you specified in your `nginx.conf` and `config.yaml` files. So if you chose `/path/to/hls`
as your HLS file location, you would put `/path/to` in the `root` option above. Make
sure that the directory you chose is readable/writeable by both the nginx user
and the user you are running `pystreaming.py` under.

Once you set this up, you will want to run `pystreaming.py` again, this time with a slightly
different set of arguments:


```
python3 pystreaming.py --config config.yaml --port 12345 --nginx-proxy 1
```

The `--nginx-proxy` command says how many hops through nginx we had to make before
we hit `pystreaming.py`. This enables us to correctly determine the IP address of remote
clients without introducing a security hole. If you set everything up correctly
you will be able to visit [http://coolstreamingsite.com](http://coolstreamingsite.com)
and view your streams! Note that you should change that domain if you are hosing this
under a different DNS entry. If you do not have a DNS entry, just use your server's
public IP address instead. Note also that if you want to use the remote control API
you should also protect the server with SSL.

## Port forwarding and Firewall

In order to reach the server from outside, open and forward ports 1935 and 80. If
you set up SSL, open and forward port 443 instead of port 80. Do not open or forward
the port you ran `pystreaming.py` on as nginx takes care of proxying requests for us.
Now, you will be able to point OBS at `rtmp://coolstreamingsite.com/live` to stream!
Make sure to change the domain to the one you are using for your server, or if you are
not using DNS, the public IP of the server.

# Streaming

Anyone that visits a streamer's page can join the chat and watch. There is currently
no authentication for normal chatters. To join as the stream host, use the same name
as the stream. You will be asked for your stream key as a password to authenticate.
So, if you were using the user `test` from the set up example, you could visit
[http://coolstreamingsite.com/test](http://coolstreamingsite.com/test) and join the
chat as `test`. You will be asked to provide the stream key `secretkey` in order to
authenticate. Once you are connected to chat, type `/help` into the chat box to see
available commands. You can assign moderators to help you moderate if you wish. Stream
hosts and moderators can mute users, and stream hosts can change the description.
Stream hosts and moderators can rename users as well, in case they choose a naughty name.
All users can chat and use actions with `/me`. Similarly, all users can change their
color with `/color` and rename themselves with `/name`. Drawings can be submitted by
clicking the "Draw" button and sketching something cute. Standard and custom emoji can
be inserted by surrounding the name of the emoji with ":" characters. Note that starting
a word with ":" will pop up an emoji type-ahead search. Similarly, starting a word with
"@" will pop up a username type-ahead search.

# Remote Control API

Rudimentary remote control over the stream is provided by a REST API. Currently it is
possible to grab general info about a stream (such as its live status, viewer count,
members in chat, description, and stream viewing password), update the description,
update the stream viewing password, send a message on behalf of the streamer, and retrieve
messages written in the chat. There is also an example API client that shows how to
operate with the remote control API. Note that basic auth is used to communicate
credentials between the API client and the remote host, so it is highly recommended to
set up SSL on the host you are running before attempting to use the remote control API.

If you want to run it, you can see what's available with the following command:

```
python3 apiclient.py --help
```

If you wanted to get the information from a streamer named "coolguy" who uses stream key
"coolkey" on the remote streaming site [https://coolstreamingsite.com](https://coolstreamingsite.com)
you would run the same command like so:

```
python3 apiclient.py https://coolstreamingsite.com --username coolguy --key coolkey getinfo
```

# Future Enhancements

 * Kick and ban from chat feature based on client IP. Not currently necessary but might become so.
 * Persistent username/account feature. Not sure how desirable this is, but its an option.
 * Word filtering support for chat. Not currently necessary but I'm sure it will end up being needed.
 * Rate limiting for chat actions. Not currently necessary but I'm sure that it will end up being needed.
 * Better front page with streamer highlights and such.
 * Better mobile support across the board.
 * Multi-theme support and theme selection.
 * Stream analytics such as chatters, viewers, duration, etc.
