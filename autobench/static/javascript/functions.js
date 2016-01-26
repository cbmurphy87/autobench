$(document).ready(function () {
    $("li.message").click(function () {
        $(this).fadeOut();
    });
});

function goBack() {
    window.history.back();
}