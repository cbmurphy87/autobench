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
            jo.show();
            $("[id*='" + this.id + "_child']").each(
                function () {
                    $(this).show();
                }
            );
            $("[id*='_child']").each(
                function() {
                    //console.log($(this));
                    $(this).hide();
                }
            );
            updateStriping();
            return;
        } else {
            //hide all the rows
            jo.hide();
            //Recusively filter the jquery object to get results.
            jo.filter(function (i, v) {
                var $t = $(this);
                if ($t.is("[id*='_child']")) {
                    console.log('false');
                    return false;
                }
                for (var d = 0; d < data.length; ++d) {
                    if ($t.is(":contains('" + data[d] + "')")) {
                        return true;
                    }
                }
                return false;
            })
            //show the rows that match.
                .show();
        }
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