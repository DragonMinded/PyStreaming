var socket = io.connect(location.protocol  + '//' + document.domain + ':' + location.port);
var username = undefined;
var connected = false;
var live = false;
var autoscroll = true;
var users = [];

// If the description contains a link, don't constantly refresh, since it can cause a slight
// flash when the link is not colored as visited.
var lastViewerCount = null;
var lastStreamDescription = null;

// Shared state between input controls.
var inputState = new InputState();

if (chatdefault != "disabled") {
    // Support previews of emoji and emotes.
    var options = [];
    for (const [key, value] of Object.entries(emojis)) {
      options.push({text: key, type: "emoji", preview: twemoji.parse(value, twemojiOptions)});
    }
    for (const [key, value] of Object.entries(emotes)) {
      options.push({text: key, type: "emote", preview: "<img class=\"emoji-preview\" src=\"" + value + "\" />"});
    }
    var emojisearchUpdate = emojisearch(inputState, '.emoji-search', '#message', options);

    // Support tab-completing users as well.
    var acusers = [];
    var autocompleteUpdate = autocomplete(inputState, '#message', options.concat(acusers));

    // Whenever user changes occur (joins/parts/renames), update the autocomplete typeahead for those names.
    var updateusers = function() {
      acusers = users.map(function(user) {
        return {text: "@" + user.username, type: "user", preview: "<span>" + escapehtml(user.username) + "</span>"};
      });
      autocompleteUpdate(options.concat(acusers));
    }

    // Whenever an emote is live-added, update the autocomplete typeahead for that emote.
    var addemote = function(key, uri) {
      emotes[key] = uri;
      options.push({text: key, type: "emote", preview: "<img class=\"emoji-preview\" src=\"" + uri + "\" />"});
      autocompleteUpdate(options.concat(acusers));
      emojisearchUpdate(options);

      // Also be sure to reload the image.
      var box = $( 'div.emote-preload' );
      box.append( '<img src="' + uri + '" />' );
    }

    // Whenever an emote is live-removed, update the autocomplet typeahead to remove that emote.
    var delemote = function(key) {
      delete emotes[key];

      var loc = 0;
      while( loc < options.length ) {
        if (options[loc].type == "emote" && options[loc].text == key) {
          options.splice(loc, 1);
        } else {
          loc ++;
        }
      }
      autocompleteUpdate(options.concat(acusers));
      emojisearchUpdate(options);
    }
} else {
    // Chat is disabled, don't waste time with typeaheads and such.
    var addemote = function(key, uri) {}
    var delemote = function(key) {}
}

// Calculate the integer scroll top of a given component.
var scrollTop = function( obj ) {
  // Sometimes the chrome/firefox calculation of scrollTopMax is off by one
  return Math.floor(obj.scrollTop) + 1;
}

// Calculate the maximum scroll top of a given component.
var scrollTopMax = function( obj ) {
  return obj.scrollHeight - obj.clientHeight;
}

var ensureScrolled = function() {
  var box = $( 'div.messages' );
  if (autoscroll) {
    box[0].scrollTop = scrollTopMax(box[0]) + 1;
  } else {
    $( 'div.new-messages-alert' ).css( 'display', 'inline-block' );
  }
}

// Add some inner HTML to the chat box.
var add = function( inner, type, color ) {
  var box = $( 'div.messages' );
  if (color != undefined) {
    box.append( '<div class="chat-message ' + type + '" style="--user-color: ' + color + '">' + inner + '</div>' );
  } else {
    box.append( '<div class="chat-message ' + type + '">' + inner + '</div>' );
  }

  ensureScrolled();
}

// Display an error in the user error box at the bottom, mostly for login.
var displayerror = function( error ) {
  var box = $( 'div.messages' );
  $( 'div.error' ).text( error );
  ensureScrolled();
}

// Remove a displayed error in the user error box at the bottom.
var clearerror = function() {
  var box = $( 'div.messages' );
  $( 'div.error' ).text( "" );
  ensureScrolled();
}

var entityMap = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
  '/': '&#x2F;',
  '`': '&#x60;',
  '=': '&#x3D;'
};

// Given a user-supplied message, escape any HTML in the message and apply emoji/emote lookups.
var escapehtml = function( str ) {
  str = String(str);
  str = str.replace(/[&<>"'`=\/]/g, function (s) {
    return entityMap[s];
  });
  Object.keys(emojis).forEach(function(emoji) {
      str = str.replaceAll(emoji, emojis[emoji]);
  });
  str = twemoji.parse(str, twemojiOptions);
  Object.keys(emotes).forEach(function(emote) {
      str = str.replaceAll(emote, "<img src='" + emotes[emote] + "' class='emote' alt='" + emote + "' />");
  });
  return str;
}

// Given an HTML color code, calculates that color's relative luminance
// Returned luminance value is on a scale from 0 to 1
var colorLuminance = function(color) {
    const rgb = Object.freeze({
      RED: 0,
      GREEN: 1,
      BLUE: 2
    });

    const channels = [0, 0, 0];
    for (let i = 0; i < 3; ++i) {
      channels[i] = parseInt(color.slice( (i*2)+1 , ((i+1)*2)+1  ), 16);
      channels[i] /= 255;

      if(channels[i] <= 0.04045){
        channels[i] /= 12.92;
      } else {
        channels[i] = ((channels[i]+0.055)/1.055) ** 2.4;
      }
    }

    let luminance = 0.2126 * channels[rgb.RED] + 0.7152 * channels[rgb.GREEN] + 0.0722 * channels[rgb.BLUE];

    return luminance;
}

// Given an HTML color code for a text color, determines if that text color
// deserves the CSS class for dark user text colors, or the CSS class for
// light user text colors.
var colorLuminanceClass = function(color) {
    let lumiThreshold = 0.5; // Defines the relative luminance threshold for considering a color light
    if ( colorLuminance(color) >= lumiThreshold ) {
        return "light-user-text-color";
    } else {
        return "dark-user-text-color";
    }
}

// Keep the socket alive, and allow accurate view counts for the stream.
var ping = function() {
  socket.emit( 'presence', {
    streamer : streamer,
  } );
}

// Grab the stream information, possibly reload the stream control if the streamer went live,
// display the info such as number of viewers and stream description. This also handles when
// a password is applied to the stream that the viewer has not inputted, to kick anyone who
// joined before a password was set.
var info = function() {
  $.get("/" + streamer + "/info", {}, function(response) {
    if (response.live) {
      if (response.count != lastViewerCount) {
        lastViewerCount = response.count;
        $( 'div.stream-count' ).html( '<img class="viewer-count-icon" alt="number of viewers" /> ' + response.count );
      }

      if (response.description != lastStreamDescription) {
        lastStreamDescription = response.description;
        $( 'div.stream-description').html( linkifyHtml(escapehtml(response.description), linkifyOptions) );
      }
    } else {
      $( 'div.stream-count' ).text( '' );
      $( 'div.stream-description').text( '' );
    }

    if (response.live != live) {
      live = response.live;
      videojs.players['my-video'].reset();
      videojs.players['my-video'].src(playlists);
      videojs.players['my-video'].load();
    }
  } ).fail(function(response) {
    if (response.status == 403) {
      // Stream password was turned on, we don't have access.
      location.reload();
    }
  } );
}

// Walks an already HTML-stripped and emojified message to see if any part of it is a reference
// to the current user. If so, wraps that chunk of text in a highlight div, but does not change
// capitalization. This allows your own name to be highlighted without rewriting how somebody
// wrote the message.
var highlight = function(msg) {
  var actualuser = escapehtml(username).toLowerCase();

  if( msg.length < actualuser.length ) {
    return msg;
  }

  var pos = 0;
  while (pos <= (msg.length - actualuser.length)) {
    if (pos > 0) {
      if (msg.substring(pos - 1, pos) != " ") {
        pos ++;
        continue;
      }
    }
    if (pos < (msg.length - actualuser.length)) {
      if (msg.substring(pos + actualuser.length, pos + actualuser.length + 1) != " ") {
        pos ++;
        continue;
      }
    }

    if (msg.substring(pos, pos + actualuser.length).toLowerCase() != actualuser) {
      pos++;
      continue;
    }

    before = '<span class="name-highlight user-item">';
    after = '</span>';
    msg = (
      msg.substring(0, pos) +
      before +
      msg.substring(pos, pos + actualuser.length) +
      after +
      msg.substring(pos + actualuser.length, msg.length)
    );

    pos += actualuser.length + before.length + after.length;
  }

  return msg;
}

// Takes an alraedy HTML-stripped and emojified message and figures out if it contains only
// emoji/emotes. If so, it makes them bigger because bigger emoji is more fun.
var embiggen = function(msg) {
    if( msg.length == 0 ) {
        return msg;
    }

    var domentry = $('<span class="wrapperelement">' + msg + '</span>');
    var text = domentry.text().trim();
    if (text.length == 0 && msg.length > 0) {
        // Emoji only, embiggen the pictures.
        domentry.find('.emoji').addClass('emoji-big').removeClass('emoji');
        domentry.find('.emote').addClass('emote-big').removeClass('emote');
        return domentry.html();
    }

    return msg;
}

// Takes any message that supports user type and outputs a user type icon for that user type.
var iconify = function(msg) {
    if( icons.indexOf(msg.type) >= 0 ) {
        return '<img class="user-type-icon ' + msg.type + '" alt="' + msg.type + '" />';
    }

    return "";
}

// Takes an already formatted and iconified username string and wraps it in a user-item div
// to ensure that the name doesn't get word-wrapped in the middle. Also allows name colors to
// be applied when needed.
var userify = function( user, color ) {
    var usecolor = color || false;
    if (usecolor) {
        return '<div class="user-item ' + colorLuminanceClass(color) + '" style="color: ' + color + '">' + user + '</div>';
    } else {
        return '<div class="user-item">' + user + '</div>';
    }
}

var setCookie = function(name,value,days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days*24*60*60*1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "")  + expires + "; path=/";
}

var getCookie = function(name) {
  return document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')?.pop() || ''
}

// Hook autoscrolling to being a the bottom of the chat.
$('div.messages').scroll(function() {
  var box = $( 'div.messages' );
  autoscroll = scrollTop(box[0]) >= scrollTopMax(box[0]);
  if (autoscroll) {
    $( 'div.new-messages-alert' ).css( 'display', 'none' );
  }
});

// Make sure we move the chat after animating pictochat.
$('#pictochat-container').on('transitionend webkitTransitionEnd oTransitionEnd', function () {
  ensureScrolled();
});

// Automatically move the chat scroll to the bottom on window resize if we're autoscrolling.
$(window).resize(function() {
  var box = $( 'div.messages' );
  if (autoscroll) {
    box[0].scrollTop = scrollTopMax(box[0]) + 1;
  }
});

// All of our websocket messages from the server are handled below.
socket.on( 'connect', function() {
  clearerror();
  $( '#login' ).on( 'submit', function( e ) {
    e.preventDefault();

    username = $( 'input.username' ).val();
    color = $( 'select.color' ).val();
    socket.emit( 'login', {
      username : username,
      streamer : streamer,
      color : color,
    } );
    updateColor(color);
  } );

  ping();
  info();
  setInterval(ping, 5000);
  setInterval(info, 5000);
} );

socket.on( 'login key required', function( msg ) {
  username = msg.username;

  clearerror();
  $( '#login' ).remove();
  $( '#admin' ).show();
  $( '#password' ).focus()

  $( '#admin' ).on( 'submit', function( e ) {
    e.preventDefault();

    let password = $( 'input.password' ).val();
    socket.emit( 'login', {
      streamer : streamer,
      username : username,
      color : color,
      key : password,
    } );
  } );
});

socket.on( 'login success', function( msg ) {
  username = msg.username;

  clearerror();
  $( '#login' ).remove();
  $( '#admin' ).remove();
  $( '#chat' ).show();
  $( '#message' ).focus()

  // Send chat message.
  $( '#chat' ).on( 'submit', function( e ) {
    e.preventDefault();

    let message = $( 'input.message' ).val();
    $( 'input.message' ).val( '' );

    socket.emit( 'message', {
      message : message,
    } );
  } );

  // Send pictochat message.
  $( '#pictochat-send' ).on( 'click', function( e ) {
    e.preventDefault();
    let canvas = $( '#pictochat-canvas' )[0];
    let src = canvas.toDataURL();
    canvas.getContext("2d").clearRect(0,0,canvas.width,canvas.height);
    $("#pictochat-send").prop("disabled", true);

    socket.emit( 'drawing', {
      src : src,
    } );
  } );
});

socket.on( 'connected', function( msg ) {
  if( connected ) {
    add( '<div class="user-joined ' + colorLuminanceClass(msg.color) + '">' + userify(iconify(msg) + escapehtml(msg.username)) + ' joined!</div>', msg.username == username ? 'self' : 'other', msg.color );
  }
  if( msg.username == username && !connected ) {
    var userlist = msg.users.map(function(user) {
        return userify(iconify(user) + escapehtml(user.username), user.color);
    });
    add(
      '<div class="command-heading connected-users">Connected users:</div> ' +
      '<div class="user-list">' + userlist.join(', ') + '</div>',
      'server',
    );
    connected = true;
  }
  users = msg.users;
  updateusers();
})

socket.on( 'server', function( msg ) {
  add( '<div class="server-message">' + escapehtml(msg.msg) + '</div>', 'server' );
})

socket.on( 'disconnected', function( msg ) {
  if( connected ) {
    add( '<div class="user-left ' + colorLuminanceClass(msg.color) + '">' + userify(iconify(msg) + escapehtml(msg.username)) + ' left!</div>', msg.username == username ? 'self' : 'other', msg.color );
  }
  users = msg.users;
  updateusers();
})

socket.on( 'userlist', function( msg ) {
  var userlist = msg.users.map(function(user) {
    return userify(iconify(user) + escapehtml(user.username), user.color);
  });
  add(
    '<div class="command-heading connected-users">Connected users:</div> ' +
    '<div class="user-list">' + userlist.join(', ') + '</div>',
    'server',
  );
})

socket.on( 'rename', function( msg ) {
  add( '<div class="user-renamed ' + colorLuminanceClass(msg.color) + '">' + userify(iconify(msg) + escapehtml(msg.oldname)) + ' is now known as ' + userify(iconify(msg) + escapehtml(msg.newname)) + '!</div>', msg.oldname == username ? 'self' : 'other', msg.color );
  if (msg.oldname == username) {
      username = msg.newname;
  }
  users = msg.users;
  updateusers();
})

socket.on( 'message received', function( msg ) {
  if( connected ) {
    if( msg.username == username ) {
      clearerror();
    }
    add(
      '<div class="chat-heading ' + colorLuminanceClass(msg.color) + '">' + userify(iconify(msg) + escapehtml(msg.username)) + '<span class="sent" /></div> ' +
      '<div class="chat-body">' + linkifyHtml(embiggen(highlight(escapehtml(msg.message))), linkifyOptions) + '</div>',
      msg.username == username ? 'self' : 'other',
      msg.color
    );
  }
})

socket.on( 'action received', function( msg ) {
  if( connected ) {
    if( msg.username == username ) {
      clearerror();
    }
    add( '<div class="chat-action ' + colorLuminanceClass(msg.color) + '">* ' + userify(iconify(msg) + escapehtml(msg.username)) + ' ' + linkifyHtml(embiggen(highlight(escapehtml(msg.message))), linkifyOptions) + '</div>', msg.username == username ? 'self' : 'other', msg.color );
  }
})

socket.on( 'drawing received', function( msg ) {
  if( connected ) {
    if( msg.username == username ) {
      clearerror();
    }
    add(
      '<div class="chat-heading ' + colorLuminanceClass(msg.color) + '">' + userify(iconify(msg) + escapehtml(msg.username)) + '<span class="drew" /></div> ' +
      '<img class="pictochat-drawing" width="' + pictochatWidth + '" height="' + pictochatHeight + '" src="' + msg.src + '"></img>', msg.username == username ? 'self' : 'other', msg.color
    );
  }
})

socket.on( 'return color', function( msg ) {
  updateColor(msg.color);
});

socket.on( 'change theme', function( msg ) {
  $('#themecss').attr('href', themelink.replace(':theme:', msg.theme));
});

socket.on( 'add emote', function( msg ) {
  addemote(msg.key, msg.uri);
});

socket.on( 'remove emote', function( msg ) {
  delemote(msg.key);
});

socket.on( 'password activated', function( msg ) {
  if( msg.username.toLowerCase() != username.toLowerCase() ) {
    // Kick all users so that they must enter the stream password. Don't kick the admin since
    // its possible to pass the password back to them as they just set it. Also, if we already
    // have the correct password saved (stream was re-passworded with same password), don't refresh
    // and instead display a message.
    $.get("/" + streamer + "/info", {}, function(response) {
      add( '<div class="server-message">' + escapehtml("Stream password has beeen set to \"" + getCookie("streampass") + "\"!") + '</div>', 'server' );
    } ).fail(function(response) {
      if (response.status == 403) {
        location.reload();
      }
    } );
  }
})

socket.on( 'password set', function( msg ) {
  // Normally only sent to the admin that set thet password, so lets make sure they
  // don't get prompted for basically forever.
  setCookie("streampass", msg.password, 1024);
})

socket.on( 'password deactivated', function( msg ) {
  if( msg.username.toLowerCase() != username.toLowerCase() ) {
    // Show the password being deactivated to everyone else but the admin.
    add( '<div class="server-message">' + escapehtml(msg.msg) + '</div>', 'server' );
  }
})

socket.on( 'error', function( msg ) {
  displayerror( msg.msg );
  console.log( msg.msg );
} );

socket.on( 'warning', function( msg ) {
  console.log( msg.msg );
} );
