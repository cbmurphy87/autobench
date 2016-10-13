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

function updateStriping() {
    var tables = document.getElementsByTagName("tbody");
    for (var i = 0, table; table = tables[i]; i++) {
        var k = 0;
        for (var j = 0, row; row = table.rows[j]; j++) {
            if (!((row.style.display === "none"))) {
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
function collapse(id) {
    $("#" + id + " > td > a > img").attr('src', '/static/pictures/plus_blue.png');
    $("#" + id + " > td > a").attr('onclick', "expand('" + id + "')");
    $("[id*='_child']").each(
        function() {
            //console.log($(this));
            $(this).hide();
        }
    );

    $("[id*='" + id + "_child']").each(
        function() {
            $(this).hide();
        }
    );
    updateStriping();
}

function expand(id) {
    $("#" + id + " > td > a").attr('onclick', "collapse('" + id + "')");
    $("#" + id + " > td > a > img").attr('src', '/static/pictures/minus_blue.png');
    $("[id*='_child']").each(
        function() {
            //console.log($(this));
            $(this).slideUp();
        }
    );
    $("[id*='" + id + "_child']").each(
        function() {
            $(this).show();
        }
    );
    updateStriping();
}

$(document).ready(function () {updateStriping()});