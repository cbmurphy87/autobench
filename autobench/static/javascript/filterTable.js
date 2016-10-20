$(document).ready(function () {

    // overwright contains function to make case insensitive
    jQuery.expr[':'].contains = function(a, i, m) {
      return jQuery(a).text().toUpperCase()
          .indexOf(m[3].toUpperCase()) >= 0;
    };

    // search text
    $("input[id^='searchInput']").keyup(function () {
        // pop number off end, if present
        var tableNum = this.id.replace('searchInput', '');
        //split the current value of searchInput
        var data = this.value.split(" ");
        //create a jquery object of the rows
        var jo = $("#fbody" + tableNum).find("tr");
        // if search field empty
        if (this.value == "") {
            console.log('empty search');
            jo.each(function () {
                jo.each(function (index, element) {
                    element.classList.remove('hidden');
                });
            });
        } else {
            jo.each(function (index, element) {
                element.classList.add('hidden');
            });
            jo.filter(function (i, v) {
                var t = $(this);
                if ($(t).is("[id^='" + t.id + "']")) {
                    return false;
                }
                for (var d = 0; d < data.length; ++d) {
                    if ($(t).is(":contains('" + data[d] + "')")) {
                        return true;
                    }
                }
                return false;
            }).each(function () {
                    $(this)[0].classList.remove('hidden');
                }
            );
        }
        updateStriping();
    }).focus(function () {
        this.value = "";
        $(this).css({
            "color": "black"
        });
        $(this).unbind('focus');
    }).css({
        "color": "#C0C0C0"
    });
});