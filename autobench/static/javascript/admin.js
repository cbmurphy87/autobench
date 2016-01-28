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