function checkout(id, next) {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (xhttp.readyState == 4 && xhttp.status == 200) {
            var response = xhttp.responseText;
            var jsonResponse = JSON.parse(response);
            var row = document.getElementById(id);
            var row_a = row.getElementsByTagName("A")[0];
            var a_img = row_a.getElementsByTagName("IMG")[0];
            // change row class if held by you
            if (jsonResponse.i_am_holder == true) {
                // change class to highlight row
                row.className = 'heldserver';
                // change link to release
                row_a.setAttribute("onclick", "return release('" + id + "','')");
                // change button to green
                a_img.src = '/static/pictures/green.png';
            } else {
                row.className = '';
                row_a.setAttribute("onclick", "return release('" + id + "','')");
                a_img.src = '/static/pictures/red.png';
            }
            // change title and button color
            row_a.title = jsonResponse.title;
        }
    };
    xhttp.open("POST", "/inventory/checkout", true);
    xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    xhttp.send(JSON.stringify({id: id, next: next}));
}

function release(id, next) {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (xhttp.readyState == 4 && xhttp.status == 200) {
            var response = xhttp.responseText;
            var jsonResponse = JSON.parse(response);
            var row = document.getElementById(id);
            // change row class if held by you
            if (jsonResponse.i_am_holder == false) {
                // change class to unhighlight row
                row.className = '';
                var row_a = row.getElementsByTagName("A")[0];
                // change link to checkout
                row_a.setAttribute("onclick", "return checkout('" + id + "','')");
                row_a.title = jsonResponse.title;
                // change image to blue circle
                var a_img = row_a.getElementsByTagName("IMG")[0];
                a_img.src = '/static/pictures/blue.png';

            } else {
                row.className = '';
                var row_a = row.getElementsByTagName("A")[0];
                var row_img = row_a.getElementsByTagName("IMG")[0];
                row_img.src = '/static/pictures/red.png';
            }
        }
    };
    xhttp.open("POST", "/inventory/release", true);
    xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    xhttp.send(JSON.stringify({id: id, next: next}));
}

function update(id, next) {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (xhttp.readyState == 4 && xhttp.status == 200) {
            alert('Updating server. Wait 30 seconds, then reload page.');
        }
    };
    xhttp.open("POST", "/inventory/update", true);
    xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    xhttp.send(JSON.stringify({id: id, next: next}));
}

function _filterTable(field) {
    var inventoryTable = document.getElementById("aaetable");
    var tbody = inventoryTable.getElementsByTagName("tbody")[0];
    var sv = field.options[field.selectedIndex].value;
    for (var i = 2, row; row = tbody.rows[i]; i++) {
        var str = row.innerHTML;
        // remove all hidden rows if "All" is selected
        if (sv == 'All') {
            row.style.display = null;
        } else {
            if (str.indexOf(sv) <= 0) {
                row.style.display='none';
            }
        }
    }
}

function updateStriping() {
    var tables = document.getElementsByTagName("tbody");
    for (var i = 0, table; table = tables[i]; i++) {
         var k = 0;
        console.log('Updating striping');
        for (var j = 0, row; row = table.rows[j]; j++) {
            if (!(row.style.display === "none")) {
                if (k % 2) {
                    row.classList.remove('even');
                    row.classList.add('odd');
                } else {
                    row.classList.remove('odd');
                    row.classList.add('even');
                }
                k++;
            }
        }
    }
}

$(document).ready(function () {updateStriping()});