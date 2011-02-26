$(function () {
    var tabContainers = $('div.panes > div');

    $('ul.tabs a').click(function () {
        console.log(this.hash);
        tabContainers.hide().filter(this.hash).show();

        $('ul.tabs a').removeClass('selected');
        $(this).addClass('selected');

        return false;
    }).filter(':first').click();
});