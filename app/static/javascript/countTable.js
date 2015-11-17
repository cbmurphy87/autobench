$(document).ready(function () {
    var count_tables = $('table.count');
    // loop over tables to count
    var total_count = [];
    for (var table_num = 0, table; table = count_tables[table_num]; table_num++) {
        // get thead to get count type and units
        var table_head = table.getElementsByTagName('thead')[0];
        var units = [];
        var ignore_column = []
        var thead_row = table_head.rows[0];
        for (var col_num = 0, col; col = thead_row.cells[col_num]; col_num++) {
            units.push(col.getAttribute('unit'));
            if (col.getAttribute('count_type') == 'ignore') {
                ignore_column.push(true);
            } else {
                ignore_column.push(false);
            }
        }
        /* ============= below this works =========== */
        var table_body = table.getElementsByTagName('tbody')[0];
        // loop over rows in table
        var row_count = []
        for (var row_num = 0, row; row = table_body.rows[row_num]; row_num++) {
            // loop over columns in row
            var col_count = 0;
            for (var col_num = 0, col; col = row.cells[col_num]; col_num++) {
                // get elements in cell with custom_count tag
                var counts = col.getElementsByClassName('custom_count');
                // loop over children to count
                for (var count_num = 0, child_count; child_count = counts[count_num]; count_num++) {
                    if (typeof total_count[col_num] === 'undefined') {
                        total_count.push(0);
                    }
                    total_count[col_num] = total_count[col_num] + parseInt(child_count.innerHTML);
                }
            }
        }
        var table_footer = table.getElementsByTagName('tfoot')[0];
        var foot_row = table_footer.rows[0];
        for (var cell_num = 0, foot; foot = foot_row.cells[cell_num]; cell_num++) {
            // do calculations on columns
            if (ignore_column[cell_num] == false) {
                var cell_unit = foot.getAttribute('unit');
                foot.innerHTML = total_count[cell_num] + " " + units[cell_num];
            }
        }
        console.log(units);
        console.log(ignore_column);
    }
});