// Copyright 2013 OpenStack Foundation
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License. You may obtain
// a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations
// under the License.

function update_graph_for_bug(main, bug) {
    var div = main.find("#bug-" + bug['number'] + " .graph");
    if (bug['fails'] > 0) {
        $.plot(div, bug['data'],
               {xaxis: {
                   mode: "time"
               }}
              );
    } else {
        div.html("No matches");
        div.css('height', 'auto');
        div.parent().css('opacity', '0.5');
    }

    // if we've updated the bug number in question, and our requested
    // location is this bug, reset the window location to visually
    // scroll us to this point.
    if ( ("#" + bug['number']) == window.location.hash ) {
        window.location.replace(window.location.href);
    }
}

function update_critical_dates(data) {
    var last_updated = new Date(data['now']);
    var last_indexed = new Date(data['last_indexed']);
    $('#last_updated').text(last_updated.toString());
    $('#last_indexed').text(last_indexed.toString());

    var hours = parseInt(data['behind'] / 60 / 60 / 1000);
    var behind = $('#behind');
    if (hours > 0) {
        behind.css('font-weight', 'bold');
        behind.text("Indexing behind by " + hours + " hours");
        $('#behind').text("Indexing behind by " + hours + " hours");
        if (hours > 0) {
            behind.css('color', 'red');
        }
    } else {
        behind.css('font-weight', 'normal');
        $('#behind').text("Up to date");
    }
}

function alert_old_generated_date() {
    var now = new Date();
    var generated_date = Date.parse($('#generated-date').text());
    var delta_hours = (now - generated_date) / 60 / 60 / 1000;
    if (delta_hours > 0) {
        var div = $('#generated-date');
        div.css('color', 'red');
        div.css('font-weight', 'bold');
        var old_text = $('#generated-date').text;
        div.text("Data is old: " + old_text);
    }

}

function update_health(data) {
    var health = $('#health');
    health.text(data['status']);
    $('#health').text(data['status']);
    if (data['status'] == 'red') {
        // TODO(mriedem): link to the cluster health details
        // http://logstash.openstack.org/elasticsearch/_cluster/health?pretty=true
        health.css('font-weight', 'bold');
    } else {
        health.css('font-weight', 'normal');
    }
    health.css('color', data['status']);
}

function update() {
    var source   = $("#bug-template").html();
    var template = Handlebars.compile(source);
    $.getJSON(data_url, function(data) {
        var buglist = data;
        // compatibility while we flip data over
        if ('buglist' in data) {
            buglist = data['buglist'];
            update_critical_dates(data);
            update_health(data);
        }

        var main = $('#main-container');
        var content = "";

        $.each(buglist, function(i, bug) {
            content += template({'bug': bug});
        });
        main.append(content);

        // The graph functions are slow, but there is actually no
        // reason to hold up the main paint thread for them, so put
        // them into an async mode to run as soon as they can. This
        // dramatically increases perceived page load speed.
        $.each(buglist, function(i, bug) {
            setTimeout(function() {
                update_graph_for_bug(main, bug);
            }, 1);
        });
    });
};

$(function() {
    update();
});
