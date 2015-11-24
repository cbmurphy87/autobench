filtertable = {
    init: function () {
        // quit if this function has already been called
        if (arguments.callee.done) return;
        // flag this function so we don't do the same thing twice
        arguments.callee.done = true;
        // kill the timer
        if (_timer) clearInterval(_timer);

        if (!document.createElement || !document.getElementsByTagName) return;

        filtertable.DATE_RE = /^(\d\d?)[\/\.-](\d\d?)[\/\.-]((\d\d)?\d\d)$/;

        forEach(document.getElementsByTagName('table'), function (table) {
            if (table.className.search(/\bfilterable\b/) != -1) {
                filtertable.makeFilterable(table);
            }
        });
    },

    makeFilterable: function (table) {
        if (table.getElementsByTagName('thead').length == 0) {
            // table doesn't have a tHead. Since it should have, create one and
            // put the first table row in it.
            the = document.createElement('thead');
            the.appendChild(table.rows[0]);
            table.insertBefore(the, table.firstChild);
        }
        // Safari doesn't support table.tHead, sigh
        if (table.tHead == null) table.tHead = table.getElementsByTagName('thead')[0];

        if (table.tHead.rows.length != 1) return; // can't cope with two header rows

        // work through each column and calculate its type
        var headrow = table.tHead.rows[0].cells;
        for (var i = 0; i < headrow.length; i++) {
            // manually override the type with a filtertable_type attribute
            if (!headrow[i].className.match(/\bunfilterable\b/)) { // skip this col
                var mtch = headrow[i].className.match(/\bfiltered_by_([a-z0-9]+)\b/);
                if (mtch) {
                    var override = mtch[1];
                }
                if (mtch && typeof filtertable["filter_" + override] == 'function') {
                    headrow[i].filtertable_filterfunction = filtertable["filter_" + override];
                } else {
                    headrow[i].filtertable_filterfunction = filtertable.guessType(table, i);
                }
                // make it clickable to filter
                headrow[i].filtertable_columnindex = i;
                headrow[i].filtertable_tbody = table.tBodies[0];

                // find filter button and attach it to click event
                var filter_button = document.getElementById('filter_button');
                dean_addEvent(filter_button, "click", filtertable.innerfilterFunction = function (e) {

                    if (this.className.search(/\bfiltertable_filtered\b/) != -1) {
                        // if we're already filtered by this column, just
                        // reverse the table, which is quicker
                        filtertable.reverse(this.filtertable_tbody);
                        this.className = this.className.replace('filtertable_filtered',
                            'filtertable_filtered_reverse');
                        this.removeChild(document.getElementById('filtertable_filterfwdind'));
                        filterrevind = document.createElement('span');
                        filterrevind.id = "filtertable_filterrevind";
                        filterrevind.innerHTML = stIsIE ? '&nbsp<font face="webdings">5</font>' : '&nbsp;&#x25B4;';
                        this.appendChild(filterrevind);
                        return;
                    }
                    if (this.className.search(/\bfiltertable_filtered_reverse\b/) != -1) {
                        // if we're already filtered by this column in reverse, just
                        // re-reverse the table, which is quicker
                        filtertable.reverse(this.filtertable_tbody);
                        this.className = this.className.replace('filtertable_filtered_reverse',
                            'filtertable_filtered');
                        this.removeChild(document.getElementById('filtertable_filterrevind'));
                        filterfwdind = document.createElement('span');
                        filterfwdind.id = "filtertable_filterfwdind";
                        filterfwdind.innerHTML = stIsIE ? '&nbsp<font face="webdings">6</font>' : '&nbsp;&#x25BE;';
                        this.appendChild(filterfwdind);
                        return;
                    }

                    // remove filtertable_filtered classes
                    theadrow = this.parentNode;
                    forEach(theadrow.childNodes, function (cell) {
                        if (cell.nodeType == 1) { // an element
                            cell.className = cell.className.replace('filtertable_filtered_reverse', '');
                            cell.className = cell.className.replace('filtertable_filtered', '');
                        }
                    });
                    filterfwdind = document.getElementById('filtertable_filterfwdind');
                    if (filterfwdind) {
                        filterfwdind.parentNode.removeChild(filterfwdind);
                    }
                    filterrevind = document.getElementById('filtertable_filterrevind');
                    if (filterrevind) {
                        filterrevind.parentNode.removeChild(filterrevind);
                    }

                    this.className += ' filtertable_filtered';
                    filterfwdind = document.createElement('span');
                    filterfwdind.id = "filtertable_filterfwdind";
                    filterfwdind.innerHTML = stIsIE ? '&nbsp<font face="webdings">6</font>' : '&nbsp;&#x25BE;';
                    this.appendChild(filterfwdind);

                    // build an array to filter. This is a Schwartzian transform thing,
                    // i.e., we "decorate" each row with the actual filter key,
                    // filter based on the filter keys, and then put the rows back in order
                    // which is a lot faster because you only do getInnerText once per row
                    row_array = [];
                    col = this.filtertable_columnindex;
                    rows = this.filtertable_tbody.rows;
                    for (var j = 0; j < rows.length; j++) {
                        row_array[row_array.length] = [filtertable.getInnerText(rows[j].cells[col]), rows[j]];
                    }
                    /* If you want a stable filter, uncomment the following line */
                    filtertable.shaker_filter(row_array, this.filtertable_filterfunction);
                    /* and comment out this one */
                    //row_array.filter(this.filtertable_filterfunction);

                    tb = this.filtertable_tbody;
                    for (var j = 0; j < row_array.length; j++) {
                        tb.appendChild(row_array[j][1]);
                    }

                    delete row_array;
                });
            }
        }
    }
}

function dean_addEvent(element, type, handler) {
    if (element.addEventListener) {
        element.addEventListener(type, handler, false);
    } else {
        // assign each event handler a unique ID
        if (!handler.$$guid) handler.$$guid = dean_addEvent.guid++;
        // create a hash table of event types for the element
        if (!element.events) element.events = {};
        // create a hash table of event handlers for each element/event pair
        var handlers = element.events[type];
        if (!handlers) {
            handlers = element.events[type] = {};
            // store the existing event handler (if there is one)
            if (element["on" + type]) {
                handlers[0] = element["on" + type];
            }
        }
        // store the event handler in the hash table
        handlers[handler.$$guid] = handler;
        // assign a global event handler to do all the work
        element["on" + type] = handleEvent;
    }
};
// a counter used to create unique IDs
dean_addEvent.guid = 1;