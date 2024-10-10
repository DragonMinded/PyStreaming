Documentation about the various CSS classes available for themes to use. In
general the easiest way to create a new theme is to start with the default
and modify to suit. The theme engine will load the top-level stream.css file
from your theme directory when the user selects it and everthing will cascade
from that. As long as you use relative resources in your css file everything
can be themed from the general site style down to the various icons atatched
to names. You can also include additional assets in your theme's directory and
reference them in your stream.css file.

# General Layout

The view is split into two main horizontal chunks. The top-level container has
the adequately named `content` class. If you need to attach CSS variables,
global fonts or other page-wide styles, this is a good place to do that. The
stream side is in a container with the `stream-pane` class, and the chat side
is in a container with the `chat-pane` class.

The element and CSS class heirarchy looks like so:

```
<div.content>
  <div.stream-pane />
  <div.chat-pane />
</div.content>
```

## Stream Components

The stream components are very simple and all found as children to the `stream-pane`
element. The video player is a `<video>` tag that lives inside a container with
the `stream` class applied. It is managed by video.js, so any documentation on
styling video.js players applies here as well.

The info section at the bottom lives inside an `info` container and consists of
three child containers. The first is the `stream-description` container that
contains the streamer-set description as text. Note that it can also include
`<img>` and `<a>` tags if the streamer uses custom emoji or links in their stream
description. The second is a `stream-padding` container that sits between the
description and viewer count. The third is a `stream-count` container that
contains an `<img>` with the class `viewer-count-icon` and no `src` as well as
text containing the stream viewer count. The `src` attribute is meant to be set
in the stream.css file so you can change it with the theme. Note that the contents
of the `stream-description` and `stream-count` containers are replaced whoesale
when they change so keep that in mind if you're attempting CSS transitions on
these elements.

The element and CSS class heirarchy looks like so:

```
<div.stream-pane>
  <div.stream>
    <video id="my-video" />
  </div.stream>
  <div.info>
    <div.stream-description />
    <div.stream-padding />
    <div.stream-count>
      <img.viewer-count-icon />
    </div.stream-count>
  </div.info>
</div.stream-pane>
```

## Chat Components

All chat components are found inside the `chat-pane` container. This container
is what should be animated using CSS transitions for handling chat hiding and
showing. Inside of it is a wrapper `chat-boundary` container that should receive
all of the chat styling that you want to provide. Depending on whether the
chatter has chosen a nickname or not, one of three `chat-inner` forms will be
visible while the other two will be hidden. They are identified by the IDs
`login`, `admin` and `chat`. In general, you can apply styling to just the top
`chat-inner` form and it will be applied to all three forms as they're visible.
Both the `login` and `admin` authentication forms have a theme dropdown with
the `theme` class. Both have a `theme-prompt` container for the text that displays
above the theme selector. Both have a `username-prompt` container for the text
that displays above the nickname selector input or the admin password input.
All three forms have an `error` container for displaying server-originated and
client-side error messages.

The `chat` form is the most complex, because this is the one where messages are
displayed and new chat messages and pictochat drawings can be created. All received
messages, be they user messages or server messages, will be placed inside the
`messages` container element. Below that is a `message-input` container which holds
the `new-message-alert` container which is displayed when a chatter is scrolled up
and a message is received. It also contains an input with the `message` class which
is where chatters type commands and new messages. Below the `message-input` container
is a `buttons-container` which contains the action buttons for "Send" and "Draw".
Below the `buttons-container` container is the previously-mentioned `error` container.
Below that is the `pictochat-container` and is described below.

The `pictochat-container` contains several classes inside it. The first is a canvas
element which is where the actual drawing takes place. Below that is the
`pictochat-controls` class which contains three buttons all with the `pictochat-buttons`
class. They can be identified with the IDs `pictochat-togglecolor`, `pictochat-clear`
and `pictochat-send`. Note that the entire `pictochat-container` is what you will
want to animate with CSS transitions if you are doing so.

The element and CSS class heirarchy looks like so:

```
<div.chat-pane>
  <div.chat-boundary>
    <form.chat-inner id="login">
      <div.theme-prompt />
      <select.theme />
      <div.username-prompt />
      <input.username />
      <select.color />
      <submit />
      <div.error />
    </form.chat-inner>
    <form.chat-inner id="admin">
      <div.theme-prompt />
      <select.theme />
      <div.username-prompt />
      <input.password />
      <submit />
      <div.error />
    </form.chat-inner>
    <form.chat-inner id="chat">
      <div.messages />
      <div.message-input>
        <div.new-messages-alert />
        <input.message />
      </div.message-input>
      <div.buttons-container>
        <button id="sendbutton" />
        <button id="drawbutton" />
      </div.buttons-container>
      <div.error />
      <div.pictochat-container>
        <canvas id="pictochat-canvas"/>
        <div.pictochat-controls>
          <button.pictochat-buttons id="pictochat-togglecolor" />
          <button.pictochat-buttons id="pictochat-clear" />
          <button.pictochat-buttons id="pictochat-send" />
        </div.pictochat-controls>
      </div.pictochat-container>
    </form.chat-inner>
  </div.chat-boundary>
</div.chat-pane>
```

### Chat Messages

The individual chat messages themselves which appear inside the `messages` container
documented above can be fairly complex, so they're broken down here in their own
section. Every single message that is received will be wrapped in a `chat-message`
container that additionally will have the `self`, `other` or `server` class to denote
whether the message originated from the current chatter, another chatter, or a server
message such as help display or a user list response. Additionally, for all messages
that are not server-generated, the CSS variable `--user-color` is set on the
`chat-message` container that matches the color of the chatter at the time of receiving
the messgae. Every message that has the user color CSS variable will also have either
the `dark-user-text-color` or `light-user-text-color` CSS class applied as well,
calculated based on the luminance of the user's color. The inner contents of each
message type is documented below.

For any user-generated message (in practice this is the "Message Received" and "Action
Received" message) that contain text, it's possible to mention another user by
including their name. In the case that the current chatter is the mentioned user,
their name will be wrapped in a `name-highlight` span element. Note that every
element that wraps a username, such as names in user lists, the name highlight element
and in the `chat-heading` elements, the element directly wrapping the name will have
the `user-item` class applied to it.

#### User Joined

The user joined message is a two-part message that contains a `user-joined` container
and a `chat-body` container that just contains text that the particular user joined.
This will have the user color variable set for use in styling. It looks like the following:

```
<div.chat-message>
  <div.user-joined />
  <div.chat-body />
</div.chat-message>
```

#### Connected Users List

The connected users list is a server-originated message that contains a `command-heading`
container for the "connected users" message and a `user-list` container that contains
a bunch of inline-styled `<div>` elements to color user names correctly. The
`command-heading` container will additionally contain a `connected-users` class to
distinguish it from other command headings. Note that this will only ever contain
the `server` class since it does not come from a user, and it will not have the
user color variable set either. It looks like the following:

```
<div.chat-message>
  <div.command-heading />
  <div.user-list />
</div.chat-message>
```

#### Server Message

The server message is a simple message that contains a `server-message` container that
only contains the content as delivered from the server. It will only ever contain the
`server` class since it does not come from a user, and it will not have the color
variable set either. It looks like the following:

```
<div.chat-message>
  <div.server-message />
</div.chat-message>
```

#### User Left

The user joined message is a two-part message that contains a `user-left` container
and a `chat-body` container that just contains text that the particular user left.
This will have the user color variable set for use in styling. It looks like the following:

```
<div.chat-message>
  <div.user-left />
  <div.chat-body />
</div.chat-message>
```

#### User Renamed

The user renamed message is a three-part message that contains a `user-renamed`
container containing the old name, a `chat-body` container that just contains text
that the particular user renamed themselves from their old name to their new namei
and a `user-renamed` container containing the new name. This will have the user
color variable set for use in styling. It looks like the following:

```
<div.chat-message>
  <div.user-renamed />
  <div.chat-body />
  <div.user-renamed />
</div.chat-message>
```

#### User Recolored

The user recolored message is a two-part message that contains a `user-recolored`
container for the name of the chatter that recolored themselves and a `chat-body`
container that contains the text that they recolored. This will have the user
color variable set for use in styling. It looks like the following:

```
<div.chat-message>
  <div.user-recolored />
  <div.chat-body />
</div.chat-message>
```

#### Message Received

The message received message is a two-part message that contains a `chat-heading`
container for the name of the chatter that sent the message and a `chat-body`
container that contains the text of the message. Note that the message body could
contain `<img>` tags for custom emoji that the user sent. This will have the user
color variable set for use in styling. It looks like the following:

```
<div.chat-message>
  <div.chat-heading />
  <div.chat-body />
</div.chat-message>
```

#### Action Received

The action received message is a two-part message that contains a `chat-action`
container for the name of the chatter that sent the message and a `chat-body`
container that contains the text of the action that they performed. Note that the
chat action could contain `<img>` tags for custom emoji that the user sent. This
will have the user color variable set for use in styling. It looks like the
following:

```
<div.chat-message>
  <div.chat-action />
  <div.chat-body />
</div.chat-message>
```

#### Drawing Received

The drawing received message is a two-part message that contains a `chat-heading`
container for the name of the chatter that sent the message and a `pictochat-drawing`
image that contains the source of the drawn image that the user sent. This will
have the user color variable set for use in styling. It looks like the following:

```
<div.chat-message>
  <div.chat-heading />
  <img.pictochat-drawing />
</div.chat-message>
```
