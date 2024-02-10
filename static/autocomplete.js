function getCursorPosition(element) {
    var el = $(element).get(0);
    if ('selectionStart' in el) {
        return el.selectionStart;
    }

    return null;
}

function autocomplete( selector, items ) {
    var displayed = false;
    var handled = false;

    $(selector).on('keydown', function(event) {
        handled = false;
        if(!displayed) {
            return;
        }

        const pos = getCursorPosition(this);
        if (pos === null) {
            return;
        }

        // Are we closing the menu?
        if(event.keyCode == 27) {
            // Close menu.
            hide();
            handled = true;
            event.preventDefault();
            return false;
        }

        // Is this a menu movement?
        if(event.keyCode == 38 || event.keyCode == 40) {
            if (event.keyCode == 38) {
                cursorup();
            } else {
                cursordown();
            }

            // Don't move the cursor
            handled = true;
            event.preventDefault();
            return false;
        }

        // Figure out if we have anything to display.
        var word = "";
        var text = $(selector).val();
        var curpos = pos;
        var curstart = 0;
        var curend = 0;
        var reWhiteSpace = new RegExp("/\s/");

        while(curpos > 0) {
            if(text[curpos - 1].trim() === '') {
                break;
            }
            curpos --;
        }
        curstart = curpos;

        while(curpos < text.length) {
            if(text[curpos].trim() === '') {
                break;
            }

            word += text[curpos];
            curpos ++;
        }
        curend = curpos;

        // Is this a menu selection?
        if(event.keyCode == 13 || event.keyCode == 9) {
            var choice = cursorselection();
            if (choice) {
                // Update text with choice, close menu.
                const newval = text.slice(0, curstart) + choice + text.slice(curend);
                $(selector).val(newval);
                hide();

                // Don't send a message or move the cursor.
                handled = true;
                event.preventDefault();
                return false;
            }
        }
    });

    $(selector).on('keyup focus click', function(event) {
        if (handled) {
            handled = false;
            return;
        }

        const pos = getCursorPosition(this);
        if (pos === null) {
            hide();
            return;
        }

        // Figure out if we have anything to display.
        var word = "";
        var text = $(selector).val();
        var curpos = pos;
        var curstart = 0;
        var curend = 0;
        var reWhiteSpace = new RegExp("/\s/");

        while(curpos > 0) {
            if(text[curpos - 1].trim() === '') {
                break;
            }
            curpos --;
        }
        curstart = curpos;

        while(curpos < text.length) {
            if(text[curpos].trim() === '') {
                break;
            }

            word += text[curpos];
            curpos ++;
        }
        curend = curpos;

        // Show if we are @ing somebody, or if we have at least 2 characters matching an emote, or if we are 2 or greater in length.
        if((word.startsWith(":") && word.length > 2) || word.startsWith('@') || (!word.startsWith(':') && word.length > 1))
        {
            word = word.toLowerCase();
            matches = items.filter(function(item) {
                return item.text.toLowerCase().startsWith(word);
            });

            if (matches.length > 0)
            {
                show(matches.slice(0, 10), matches.length > 10);
                return;
            }
        }

        hide();
    });

    $(selector).on('focusout', function() {
        hide();
    });

    $(window).resize(function() {
        if (displayed) {
            show();
        }
    });

    function hide() {
        displayed = false;

        $('div.autocomplete').remove();
    }

    function show(items, additional) {
        if ($('div.autocomplete').length != 0) {
            hide();
        }

        // Construct element
        displayed = true;

        $('<div class="autocomplete"></div>').appendTo('body');

        items.forEach(function(item) {
            if(item.text.startsWith('@')) {
                item = item.slice(1);
            }
            $( '<div class="autocomplete-element"></div>' ).html(item.preview + "&nbsp;" + item.text).appendTo('div.autocomplete');
        });

        if( additional ) {
            $('<div class="autocomplete-additional">...</div>').appendTo('div.autocomplete');
        }

        cursordown();

        // Position it!
        const offset = $(selector).offset();
        const width = $(selector).outerWidth();
        var height = 0;
        $('div.autocomplete-element').each(function(i) {
            height += $(this).height();
        });
        $('div.autocomplete-additional').each(function(i) {
            height += $(this).height();
        });

        $('div.autocomplete').offset({top: offset.top - (height + 2), left:offset.left});
        $('div.autocomplete').width(width - 2);
        $('div.autocomplete').height(height);
    }

    function cursorup() {
        // Try to move cursor up.
        var element = $('div.autocomplete-element.selected');
        if (element.length != 0) {
            element.removeClass('selected');
            element.prev().addClass('selected');
        }

        // Just select the last element if we looped around or have no selection.
        var element = $('div.autocomplete-element.selected');
        if (element.length == 0) {
            var elements = $('div.autocomplete-element');
            $(elements[elements.length - 1]).addClass('selected');
        }
    }

    function cursordown() {
        // Try to move cursor down.
        var element = $('div.autocomplete-element.selected');
        if (element.length != 0) {
            element.removeClass('selected');
            element.next().addClass('selected');
        }

        // Just select the last element if we looped around or have no selection.
        var element = $('div.autocomplete-element.selected');
        if (element.length == 0) {
            var elements = $('div.autocomplete-element');
            $(elements[0]).addClass('selected');
        }
    }

    function cursorselection() {
        return $('div.autocomplete-element.selected').text();
    }

    function update(newitems) {
        items = newitems;
    }

    return update;
}
