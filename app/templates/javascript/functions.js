$(document).ready(function () {
    $("button#flash").click(function () {
        $("div#flashedmessages").fadeOut();
    });
    $("li.message").click(function () {
        $(this).toggle("slow", "linear");
    });
});