function delete_project(project_id) {
    if (confirm('Are you sure you want to remove project' + project_id + '?')) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (xhttp.readyState == 4) {
                if (xhttp.status == 200) {
                    location.reload();
                    alert(xhttp.responseText);
                } else {
                    alert('Failed to remove status: ' + xhttp.status);
                }
            }
        };
        xhttp.open("POST", "/projects/delete", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({project_id: project_id}));
    }
}

function remove_member(project_id, member_id, name) {
    if (confirm('Are you sure you want to remove ' + name + ' from this project?')) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (xhttp.readyState == 4) {
                if (xhttp.status == 200) {
                    location.reload();
                    alert(xhttp.responseText);
                } else {
                    alert('Failed to remove member: ' + xhttp.status);
                }
            }
        };
        xhttp.open("POST", "/projects/" + project_id + "/remove_member", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({member_id: member_id}));
    }
}

function remove_server(project_id, server_id) {
    if (confirm('Are you sure you want to remove server ' + server_id + ' from this project?')) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (xhttp.readyState == 4) {
                if (xhttp.status == 200) {
                    location.reload();
                    alert(xhttp.responseText);
                } else {
                    alert('Failed to remove member: ' + xhttp.status);
                }
            }
        };
        xhttp.open("POST", "/projects/" + project_id + "/remove_server", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({server_id: server_id}));
    }
}

function remove_status(project_id, status_id) {
    if (confirm('Are you sure you want to remove status' + status_id + ' from this project?')) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function () {
            if (xhttp.readyState == 4) {
                if (xhttp.status == 200) {
                    location.reload();
                    alert(xhttp.responseText);
                } else {
                    alert('Failed to remove status: ' + xhttp.responseText);
                }
            }
        };
        xhttp.open("POST", "/projects/" + project_id + "/remove_status", true);
        xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhttp.send(JSON.stringify({status_id: status_id}));
    }
}