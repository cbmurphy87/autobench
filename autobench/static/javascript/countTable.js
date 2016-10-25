$(document).ready(function () {counttable()});

function counttable() {
    var count_tables = $('table.count');
    // loop over tables to count
    for (var table_num = 0, table; table = count_tables[table_num]; table_num++) {
        var total_count = [];
        var count_type = '';
        var unique_entries = [];
        // get tbody
        var table_body = table.getElementsByTagName('tbody')[0];
        // if no body, return
        if (table_body.length < 1) {
            console.log('Cannot count empty body.');
            return;
        }
        // insert tfoot if not present and there is a body
        var tfeet = table.getElementsByTagName('tfoot');
        if (tfeet.length < 1) {
            var footer = table.createTFoot();
            var fr = footer.insertRow(0);
        }
        // insert row into tfoot if none present
        var tf = tfeet[0];
        if (tf.rows.length == 0) {
            tf.insertRow();
        }
        var fr = tf.rows[0];
        // insert blank cells if not present
        for (var i = 0; i < table.rows[0].cells.length; i++) {
            if (typeof fr.cells[i] == 'undefined') {
                fr.appendChild(document.createElement('th'));
            }
        }
        // get thead and set arrays for units and ignored columns
        var table_head = table.getElementsByTagName('thead')[0];
        var units = [];
        var ignore_column = [];
        var count_types = [];
        // loop over thead to get units, count type, and ignore rows
        var thead_row = table_head.rows[0];
        for (var col_num = 0, col; col = thead_row.cells[col_num]; col_num++) {
            var unit = col.getAttribute('unit');
            units.push(unit);
            count_type = col.getAttribute('count_type');
            count_types.push(count_type);
            if (count_types[col_num] == 'ignore') {
                ignore_column.push(true);
            } else {
                ignore_column.push(false);
            }
            // add empty arrays for unique entries
            unique_entries.push([]);
        }

        // loop over rows in tbody
        for (var row_num = 0, row; row = table_body.rows[row_num]; row_num++) {
            // loop over non-hidden columns in row
            if (($(row).css('display') == 'none') || row.classList.contains('hidden')) {
                continue;
            }
            for (var col_num = 0, col; col = row.cells[col_num]; col_num++) {
                // initialize column in total_counts
                var num_value = 0;
                if (typeof total_count[col_num] === 'undefined') {
                    total_count.push(0);
                }
                // get elements in cell with custom_count tag, else innerHTML
                var counts = col.getElementsByClassName('custom_count');
                if (counts.length == 0) {
                    counts = col.children;
                }
                if (counts.length >= 1) {
                    // loop over children of cell to count
                    var cell_count = 0;
                    for (var count_num = 0, child_count; child_count = counts[count_num]; count_num++) {
                        // if unit 'count', simply add one
                        if (count_types[col_num] == 'count'
                            || typeof count_types[col_num] == null
                            || count_types[col_num] == null) {
                            cell_count = cell_count + 1;
                        } else if (count_types[col_num] == 'unique') {
                            if (unique_entries[col_num].indexOf(child_count.innerHTML) < 0) {
                                unique_entries[col_num].push(child_count.innerHTML);
                            }
                        } else if (count_types[col_num] == 'sum') {
                            num_value = parseInt(child_count.innerHTML);
                            if (!isNaN(num_value)) {
                                cell_count = cell_count + num_value;
                            }
                        }
                    }
                    total_count[col_num] = total_count[col_num] + cell_count;
                }
            }
        }
        var table_footer = table.getElementsByTagName('tfoot')[0];
        var foot_row = table_footer.rows[0];
        for (var cell_num = 0, foot; foot = foot_row.cells[cell_num]; cell_num++) {
            // do add data to footer
            count_type = count_types[cell_num];
            if (ignore_column[cell_num] == false) {
                // get values and units
                var value = total_count[cell_num];
                var unit = units[cell_num];
                if (unit == null) {
                    unit = 'none'
                }
                // reduce byte units to largest unit
                if (unit.toLowerCase() == 'mb') {
                    if (value >= 1000) {
                        value = value / 1000;
                        unit = 'GB';
                    }
                }
                if (unit.toLowerCase() == 'gb') {
                    if (value >= 1000) {
                        value = value / 1000;
                        unit = 'TB';
                    }
                }
                if (unit.toLowerCase() == 'tb') {
                    if (value >= 1000) {
                        value = value / 1000;
                        unit = 'PB';
                    }
                }
                // set values
                if (count_type == 'unique') {
                    foot.innerHTML = unique_entries[cell_num].length;
                    foot.title = 'Number of unique values.';
                } else if (typeof value == 'undefined') {
                    foot.innerHTML = '';
                } else if (unit == 'none' || unit == null) {
                    foot.innerHTML = value;
                } else {
                    foot.innerHTML = Math.round(value * 100) / 100 + " " + unit.toUpperCase();
                }
                if (count_type == 'sum') {
                    foot.title = 'Sum of values.';
                } else if (count_type == 'count') {
                    foot.title = 'Total count of rows.';
                }
            }
        }
    }
}