function getCursorStart(element) {
    var el = $(element).get(0);
    if ('selectionStart' in el) {
        return el.selectionStart;
    }

    return null;
}

function getCursorEnd(element) {
    var el = $(element).get(0);
    if ('selectionEnd' in el) {
        return el.selectionEnd;
    }

    return null;
}

function emojisearch(state, button, textbox, items) {
    var displayed = false;
    var lastCategory = "";

    // Register a callback for controlling global state.
    state.registerStateChangeCallback(function(state) {
    });

    // Create our picker, hide it.
    $('<div class="emojisearch"></div>')
        .attr("style", "display:none;")
        .appendTo('body');
    $('<div class="emojisearch-container"></div>').appendTo('div.emojisearch');
    $('<div class="emojisearch-typeahead"></div>')
        .html('<input type="text" id="emojisearch-text" placeholder="search" />')
        .appendTo('div.emojisearch-container');
    $('<div class="emojisearch-categories"></div>')
        .appendTo('div.emojisearch-container');
    $('<div class="emojisearch-content"></div>')
        .appendTo('div.emojisearch-container');

    // Filter out categories.
    var categories = {};
    Object.keys(window.emojicategories).forEach(function(category) {
        categories[category] = [];

        Object.keys(window.emojicategories[category]).forEach(function(subcategory) {
            window.emojicategories[category][subcategory].forEach(function(emoji, i) {
                categories[category].push(":" + emoji.toLowerCase() + ":");
            });
        });
    });

    // Add custom emoji if they exist.
    items.forEach(function(item, i) {
        if (item.type != "emote") {
            return;
        }

        if (!categories.hasOwnProperty("Custom")) {
            categories["Custom"] = []
        }

        categories["Custom"].push(item.text.toLowerCase());
    });

    // Find icons for categories.
    var catkeys = {};
    Object.keys(categories).forEach(function(category) {
        catkeys[categories[category][0]] = "";
    });

    // Make a mapping of the emojis and emotes.
    var emojimapping = {}
    items.forEach(function(item, i) {
        var text = item.text.toLowerCase();
        if (catkeys.hasOwnProperty(text)) {
            catkeys[text] = item.preview;
        }
        emojimapping[text] = item;
    });

    // Actually render the categories.
    Object.keys(categories).forEach(function(category, i) {
        var first = categories[category][0];
        var preview = catkeys[first];

        $('<div class="emojisearch-category"></div>')
            .attr("category", category)
            .html(preview)
            .appendTo('div.emojisearch-categories');

        categories[category].forEach(function(item, i) {
            if (emojimapping.hasOwnProperty(item)) {
                $('<div class="emojisearch-element"></div>')
                    .attr("text", emojimapping[item].text)
                    .attr("category", category)
                    .html(emojimapping[item].preview)
                    .appendTo('div.emojisearch-content');
            }
        });
    });

    // Set up category selection.
    $("div.emojisearch-category").click(function() {
        // Don't allow selection when search is happening.
        var searchInput = $("#emojisearch-text").val();

        if (searchInput != "") {
            return;
        }

        var category = $(this).attr("category");
        lastCategory = category;

        $("div.emojisearch-category").each(function(i, elem) {
            var elemCat = $(elem).attr("category");
            $(elem).removeClass("selected");
            if (elemCat == category) {
                $(elem).addClass("selected");
            }
        });

        $("div.emojisearch-element").each(function(i, elem) {
            var elemCat = $(elem).attr("category");
            if (elemCat == category) {
                $(elem).show();
            } else {
                $(elem).hide();
            }
        });

        // Make sure to scroll to the top of the visible list.
        $("div.emojisearch-content").scrollTop(0);
    });

    // Select first emoji category.
    $("div.emojisearch-category")[0].click();

    // Handle searching for an emoji.
    $("#emojisearch-text").on('input', function() {
        var searchInput = $(this).val().toLowerCase();

        if (searchInput == "") {
            // Erased search, put us back to normal.
            $("div.emojisearch-category").each(function(i, elem) {
                var elemCat = $(elem).attr("category");
                if (elemCat == lastCategory) {
                    $(elem).click();
                }
            });
            return;
        }

        // Make sure all categories are highlighted.
        $("div.emojisearch-category").each(function(i, elem) {
            if (!$(elem).hasClass("selected")) {
                $(elem).addClass("selected");
            }
        });

        $("div.emojisearch-element").each(function(i, elem) {
            var elemText = $(elem).attr("text").toLowerCase();
            if (elemText.includes(searchInput)) {
                $(elem).show();
            } else {
                $(elem).hide();
            }
        });
    });

    // Handle selecting an emoji.
    $(".emojisearch-element").click(function() {
        var emoji = $(this).attr("text");
        var textcontrol = $(textbox);

        var start = getCursorStart(textcontrol);
        var end = getCursorEnd(textcontrol);
        if (end === null) {
            end = start;
        }

        if (start !== null && end !== null) {
            var val = textcontrol.val();

            const newval = val.slice(0, start) + emoji + val.slice(end);
            textcontrol.val(newval);
            textcontrol.setCursorPosition(start + emoji.length);
        }

        hide();
        textcontrol.focus();
    });

    $(button).click(function () {
        if (displayed) {
            hide();
        } else {
            show();
        }
    });

    function show() {
        // Construct element
        displayed = true;
        $('div.emojisearch').show();

        // Broadcast that we're open.
        state.setState("search");

        // Position ourselves!
        const offset = $(textbox).offset();
        const width = $(textbox).outerWidth();
        const height = $('div.emojisearch').height();

        $('div.emojisearch').offset({top: offset.top - (height + 2), left:offset.left});
        $('div.emojisearch').width(width - 2);

        // Make sure search typeahead is focused.
        $('#emojisearch-text').focus();

        // Make sure the emoji button stays highlighted.
        if (!$(button).hasClass("opened")) {
            $(button).addClass("opened");
        }
    }

    function hide() {
        displayed = false;

        // Broadcast that we're closed.
        if(state.current == "search") {
            state.setState("empty");
        }

        // Hide our top level.
        $('div.emojisearch').hide();

        // Also make sure search is cleared.
        var searchVal = $("#emojisearch-text").val();
        if (searchVal != "") {
            $("#emojisearch-text").val("");

            // Erased search, put us back to normal.
            $("div.emojisearch-category").each(function(i, elem) {
                var elemCat = $(elem).attr("category");
                if (elemCat == lastCategory) {
                    $(elem).click();
                }
            });
        }

        // Also make sure the emoji button isn't highlighted anymore.
        if ($(button).hasClass("opened")) {
            $(button).removeClass("opened");
        }
    }

    $(window).resize(function() {
        if (displayed) {
            show();
        }
    });

    function update(newitems) {
        items = newitems;
    }

    return update;
}
