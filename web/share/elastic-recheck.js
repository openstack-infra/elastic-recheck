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

function graphite_moving_avg(job, color) {
    var time = '5hours';
    var graph = "color(alias(movingAverage(asPercent(";
    graph += "stats.zuul.pipeline.gate.job." + job + ".FAILURE,";
    graph += "sum(stats.zuul.pipeline.gate.job." + job + ".{SUCCESS,FAILURE})";
    graph += "),'" + time + "'), '" + job + "'),'" + color + "')";
    return graph;
}

function graphite_hit_count(job, color) {
    var time = '5hours';
    var graph = "color(alias(hitcount(";
    graph += "sum(stats.zuul.pipeline.gate.job." + job + ".{SUCCESS,FAILURE})";
    graph += ",'" + time + "'), '" + job + "'),'" + color + "')";
    return graph;
}

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

function update() {
    var source   = $("#bug-template").html();
    var template = Handlebars.compile(source);
    $.getJSON(data_url, function(data) {
        var buglist = data;
        // compatibility while we flip data over
        if ('buglist' in data) {
            buglist = data['buglist'];
            update_critical_dates(data);
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
        // dramatically increases percevied page load speed.
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
