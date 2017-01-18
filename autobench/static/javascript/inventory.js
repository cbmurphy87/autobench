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
            if (!((row.style.display === "none") || row.matches("[class*='hidden']"))) {
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
function collapse(parameters) {
    var id = parameters.id;
    console.log('Collapse ' + id);
    if (parameters.collapseAll === undefined) {
        parameters.collapseAll = false;
    }
    var el = document.getElementById(id);
    console.log(el.classList);
    el.classList.remove('expanded');
    var image = el.getElementsByTagName('img')[0];
    image.parentElement.setAttribute('onclick', "expand({id:'" + id + "'})");
    console.log(image);
    var image_src = image.getAttribute('src');
    var new_image_src = image_src.replace("minus", "plus");
    image.setAttribute('src', new_image_src);
    $("[id*='" + id + "_child']").each(
        function () {
            console.log('hiding: ' + $(this));
            $(this).hide();
        }
    );
    if (parameters.collapseAll) {
        $(".expanded").each(
            function () {
                //console.log($(this));
                console.log($(this));
                collapse({id:$(this).id, collapseAll:false});
            }
        );
    }
    updateStriping();
}

function expand(parameters) {
    var id = parameters.id;
    if (parameters.collapseAll === undefined) {
        parameters.collapseAll = false;
    }
    var el = document.getElementById(id);
    console.log(el);
    el.classList.add('expanded');
    var image = el.getElementsByTagName('img')[0];
    console.log(image);
    image.parentElement.setAttribute('onclick', "collapse({id:'" + id + "', collapseAll:true})");
    var image_src = image.getAttribute('src');
    var new_image_src = image_src.replace("plus", "minus");
    console.log(new_image_src);
    if (parameters.collapseAll)
    {
        collapse({"id":id, "collapseAll":true});
    }
    image.setAttribute('src', new_image_src);
    $("[id*='" + id + "_child']").each(
        function() {
            console.log('showing: ' + $(this));
            $(this).show();
        }
    );
    updateStriping();
}

$(document).ready(function () {
        updateStriping();
        $("#room_input").change(function () {
            console.log('changed room');
            var selection = this.options[this.selectedIndex].value;
            if (selection == '__None') {
                document.getElementById("rack_input").disabled = true;
                document.getElementById("rack_input").value = '__None';
            } else {
                document.getElementById("rack_input").disabled = false;
            }
            var e = document.getElementById("room_input");
            var room_id = e.value;
            var xhttp = new XMLHttpRequest();
            xhttp.onreadystatechange = function () {
                if (xhttp.readyState == 4 && xhttp.status == 200) {
                    document.getElementById("rack_input").innerHTML = xhttp.responseText;
                }
            };
            xhttp.open("POST", "/admin/racks/get", true);
            xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
            xhttp.send(JSON.stringify({room_id: room_id}));
        });
        $("#rack_input").change(function () {
            console.log('changed rack');
            var selection = this.options[this.selectedIndex].value;
            if (selection == '__None') {
                document.getElementById("u_input").disabled = true;
                document.getElementById("u_input").value = '__None';
            } else {
                document.getElementById("u_input").disabled = false;
            }
            var e = document.getElementById("rack_input");
            var rack_id = e.value;
            var xhttp = new XMLHttpRequest();
            xhttp.onreadystatechange = function () {
                if (xhttp.readyState == 4 && xhttp.status == 200) {
                    document.getElementById("u_input").innerHTML = xhttp.responseText;
                }
            };
            xhttp.open("POST", "/admin/rack_units/get", true);
            xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
            xhttp.send(JSON.stringify({rack_id: rack_id}));
        });
    }
);