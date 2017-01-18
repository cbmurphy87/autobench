function delete_user(user_name) {
    if (confirm('Are you sure you want to delete user ' + user_name + '?')) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (xhttp.readyState == 4) {
                if (xhttp.status == 200) {
                    var json_response = JSON.parse(xhttp.responseText);
                    console.log('json: ' + json_response);
                    var message = json_response['message'];
                    console.log('message: ' + message);
                    alert(message);
                    location.reload();
                } else {
                    alert('Failed to remove status: ' + xhttp.status);
                }
            }
        };
        xhttp.open("POST", "/admin/users/delete", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({user_name: user_name}));
    }
}

function remove_group_member(group_id, user_name) {
    if (confirm('Are you sure you want to remove user ' + user_name + ' from the group?')) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (xhttp.readyState == 4) {
                if (xhttp.status == 200) {
                    var json_response = JSON.parse(xhttp.responseText);
                    var message = json_response['message'];
                    alert(message);
                    location.reload();
                } else {
                    alert('Failed to remove status: ' + xhttp.status);
                }
            }
        };
        xhttp.open("POST", "/admin/groups/" + group_id + "/remove_member", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({user_name: user_name}));
    }
}

function remove_group_server(group_id, server_id) {
    if (confirm('Are you sure you want to remove server ' + server_id + ' from the group?')) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (xhttp.readyState == 4) {
                if (xhttp.status == 200) {
                    var json_response = JSON.parse(xhttp.responseText);
                    var message = json_response['message'];
                    alert(message);
                    location.reload();
                } else {
                    alert('Failed to remove status: ' + xhttp.status);
                }
            }
        };
        xhttp.open("POST", "/admin/groups/" + group_id + "/remove_server", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({server_id: server_id}));
    }
}

function delete_group(gid) {
    if (confirm("Delete group " + gid + "?") == true) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function() {
            if (xhttp.readyState == 4 && xhttp.status == 200) {
                window.location = "/admin";
            }
        };
        xhttp.open("POST", "/admin/groups/delete", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({gid: gid}));
    }
}

function delete_room(id) {
    if (confirm("Delete room " + id + "?") == true) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function() {
            if (xhttp.readyState == 4 && xhttp.status == 200) {
                window.location = "/admin";
            }
        };
        xhttp.open("POST", "/admin/rooms/delete", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({id: id}));
    }
}

function delete_rack(id,next) {
    if (confirm("Delete rack " + id + "?") == true) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function() {
            if (xhttp.readyState == 4 && xhttp.status == 200) {
                window.location = next;
            }
        };
        xhttp.open("POST", "/admin/racks/delete", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({id: id}));
    }
}