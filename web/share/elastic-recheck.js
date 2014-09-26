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
    $.getJSON(data_url, function(data) {
	var seen = [];
        var buglist = data;
        // compatibility while we flip data over
        if ('buglist' in data) {
            buglist = data['buglist'];
            update_critical_dates(data);
        }

	$.each(buglist, function(i, bug) {
	    var id = 'bug-'+bug['number'];
	    seen.push(id);
	    var div = $('#'+id);

	    if (!div.length) {
		div = $('<div/>', {'id': id, 'class': 'bug-container'});
		div.appendTo($('#main-container'));
		$('<h2/>', {text: 'Bug ' + bug['number'] + " - " + bug['bug_data']['name']}).appendTo(div);
                $('<h3/>', {
                    text: bug['fails24'] + ' fails in 24hrs / ' + bug['fails'] + ' fails in 10 days'
                }).appendTo(div);
                $('<h3/>', {
                    text: 'Projects: ' + bug['bug_data']['affects']
                }).appendTo(div);
                var reviews = bug['bug_data']['reviews'];
                if (reviews.length>0) {
                    $('<h3/>', {
                        text: 'Open reviews: ',
                        style:'font-weight: bold;'
                    }).appendTo($('<span/>', {
                        'class': 'extlink'
                    }).appendTo(div));
                }
                for (var i = 0; i < reviews.length ; i++) {
                        $('<a/>', {
                            href: 'https://review.openstack.org/#/c/'+reviews[i],
                            style:'font-weight: bold;',
                            text: reviews[i]
                        }).appendTo($('<span/>', {
                            'class': 'extlink'
                        }).appendTo(div));

                }
		$('<div/>', {'class': 'graph'}).appendTo(div);
		$('<a/>', {
		    href: 'http://logstash.openstack.org/#'+bug['logstash_query'],
		    text: 'Logstash'
		}).appendTo($('<span/>', {
		    'class': 'extlink'
		}).appendTo(div));
		$('<a/>', {
		    href: 'https://bugs.launchpad.net/bugs/'+bug['number'],
		    text: 'Launchpad'
		}).appendTo($('<span/>', {
		    'class': 'extlink'
		}).appendTo(div));
	    }
	    div = div.find(".graph");

	    if (bug['data'].length > 0) {
		$.plot(div, bug['data'],
		       {xaxis: {
			   mode: "time"
		       }}
		      );
	    } else {
		div.html("No matches");
	    }

	});
	$.each($('.bug-container'), function(i, container) {
	    if (seen.indexOf(container.id) == -1) {
		container.remove();
	    }
	});
    });
}

$(function() {
    update();
});
