#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""This module handles report creation for Patrick Mooney's program
network-reporter. Like the rest of network-reporter, this module is copyright
2017 by Patrick Mooney. It is licensed under the GNU GPL, either version 3 or,
at your option, any later version. See the file LICENSE for details.
"""


import datetime, glob, inspect, os, pickle, statistics

from config import *

import patrick_logger       # https://github.com/patrick-brian-mooney/python-personal-library
from patrick_logger import log_it


# Once all of the usability tests have been run, the overall network problem score is the largest problem score
# assigned by any test that the ping transcript has failed. (The operating theory here is we should be recording the
# level of the problem that has the biggest impact on usability.

usability_tests = [
    {'test_name': 'Packet loss above 1%',
     'test': lambda data: int(data['packet_loss'].strip().strip('%').strip()) > 1,
     'problem_level': 1,
     'data_keys_to_report': ['packet_loss'],
     'test_group': 'packet_loss'},
    {'test_name': 'Packet loss above 3%',
     'test': lambda data: int(data['packet_loss'].strip().strip('%').strip()) > 3,
     'problem_level': 2,
     'data_keys_to_report': ['packet_loss'],
     'test_group': 'packet_loss'},
    {'test_name': 'Packet loss above 6%',
     'test': lambda data: int(data['packet_loss'].strip().strip('%').strip()) > 6,
     'problem_level': 3,
     'data_keys_to_report': ['packet_loss'],
     'test_group': 'packet_loss'},
    {'test_name': 'Packet loss above 13%',
     'test': lambda data: int(data['packet_loss'].strip().strip('%').strip()) > 13,
     'problem_level': 4,
     'data_keys_to_report': ['packet_loss'],
     'test_group': 'packet_loss'},
    {'test_name': 'Packet loss above 25%',
     'test': lambda data: int(data['packet_loss'].strip().strip('%').strip()) > 25,
     'problem_level': 5,
     'data_keys_to_report': ['packet_loss'],
     'test_group': 'packet_loss'},

    {'test_name': 'Average packet RTT above 200 ms',
     'test': lambda data: float(data['avg']) > 200,
     'problem_level': 1,
     'data_keys_to_report': ['avg'],
     'test_group': 'high RTT'},
    {'test_name': 'Average packet RTT above 500 ms',
     'test': lambda data: float(data['avg']) > 500,
     'problem_level': 2,
     'data_keys_to_report': ['avg'],
     'test_group': 'high RTT'},
    {'test_name': 'Average packet RTT above 1000 ms',
     'test': lambda data: float(data['avg']) > 1000,
     'problem_level': 3,
     'data_keys_to_report': ['avg'],
     'test_group': 'high RTT'},
    {'test_name': 'Average packet RTT above 2000 ms',
     'test': lambda data: float(data['avg']) > 2000,
     'problem_level': 4,
     'data_keys_to_report': ['avg'],
     'test_group': 'high RTT'},
    {'test_name': 'Average packet RTT above 5000 ms',
     'test': lambda data: float(data['avg']) > 5000,
     'problem_level': 5,
     'data_keys_to_report': ['avg'],
     'test_group': 'high RTT'},

    {'test_name': 'Jitter above 100%',
     'test': lambda data: (float(data['mdev'].strip().strip('ms').strip()) / float(data['avg']) ) > 1,
     'problem_level': 1,
     'data_keys_to_report': ['mdev', 'avg'],
     'test_group': 'high jitter'},
    {'test_name': 'Jitter above 150%',
     'test': lambda data: (float(data['mdev'].strip().strip('ms').strip()) / float(data['avg']) ) > 1.5,
     'problem_level': 2,
     'data_keys_to_report': ['mdev', 'avg'],
     'test_group': 'high jitter'},
    {'test_name': 'Jitter above 200%',
     'test': lambda data: (float(data['mdev'].strip().strip('ms').strip()) / float(data['avg']) ) > 2,
     'problem_level': 3,
     'data_keys_to_report': ['mdev', 'avg'],
     'test_group': 'high jitter'},
    {'test_name': 'Jitter above 250%',
     'test': lambda data: (float(data['mdev'].strip().strip('ms').strip()) / float(data['avg']) ) > 2.5,
     'problem_level': 4,
     'data_keys_to_report': ['mdev', 'avg'],
     'test_group': 'high jitter'},
    {'test_name': 'Jitter above 300%',
     'test': lambda data: (float(data['mdev'].strip().strip('ms').strip()) / float(data['avg']) ) > 3,
     'problem_level': 5,
     'data_keys_to_report': ['mdev', 'avg'],
     'test_group': 'high jitter'},

    {'test_name': 'Fundamental networking errors',
     'test': lambda data: 'errors' in data,
     'problem_level': 4,
     'data_keys_to_report': ['errors'],
     'test_group': 'unreachable'},
]

def daily_report_template():
    """Returns a markdown template for the daily reports. This template will include
    percent-codes for information to be filled in by the calling function.
    """
    ret = """
# Network Quality Report for %s

%s

## Usability problem log

%s

## Tests applied to ping transcripts

%s
"""  # Substitute in: date on which data was collected; overall summary; usability problem log, description of ping rules
    return ret

def daily_summary(data):
    """Returns an overall summary for the day's performance."""
    trans, rec = data['packets_transmitted_today'], data['packets_received_today']
    all_pings = [][:]
    for i in data['ping_transcripts']:
        if 'log' in data['ping_transcripts'][i]:
            for n in data['ping_transcripts'][i]['log']:
                try:
                    all_pings += [ float(n['time']) ]
                except KeyError:
                    pass            # If we didn't record it, don't count it toward the average calculation. Probably there was a DNS lookup failure or such.
    drop_pct = 100 * ((trans-rec)/trans) if (trans > 0) else 0
    return """Today, <code>network-monitor</code> transmitted %d and received %d packets; that's an overall packet loss rate of %.4f%%. As of the end of data recording on that day, the test interval was %d minutes and each test attempted to transmit %d packets.

### Overall statistics for all ping tests:

<dl>
<dt>min</dt><dd>%.4f</dd>
<dt>avg</dt><dd>%.4f</dd>
<dt>max</dt><dd>%.4f</dd>
<dt>std dev</dt><dd>%.4f</dd>
</dl>
""" % (trans, rec, drop_pct, interval_between_pings, number_of_packets,
       min(all_pings) if (len(all_pings) > 0) else 0,
       sum(all_pings)/len(all_pings) if (len(all_pings) > 0) else 0,
       max(all_pings) if (len(all_pings) > 0) else 0,
       statistics.stdev(all_pings) if (len(all_pings) > 0) else 0,
    )

def problem_log(data):
    """Returns a markdown fragment detailing the usability events logged in DATA."""
    ret = """There were %d network usability events:

* %d events at level 2
* %d events at level 3
* %d events at level 4
* %d events at level 5

### Entire log

Here follows a list of all logged problems. Note that failures to log are not reported; currently,
there are several known reasons why logging fails occasionally. Even worse, the only way to detect these problems at
present is to inspect the raw (binary) log files by reading them with the <code>pickle</code> module in Python 3.5+.
Too, logging often begins and ends abruptly because development is still occurring. This also means that the exact
data format written to the raw files still changes occasionally.

All of this is to say that this log file is still documenting an experimental system; part of the aim of this
particular log file that you are reading right now is to help increase the stability of that system. The above
disclaimers will gradually disappear or be rewritten as the system approaches a more finalized form.
""" % (len([dict(i) for i in data['usability_events'].values() if i['worst_problem'] == 2]),
       len([dict(i) for i in data['usability_events'].values() if i['worst_problem'] == 3]),
       len([dict(i) for i in data['usability_events'].values() if i['worst_problem'] == 4]),
       len([dict(i) for i in data['usability_events'].values() if i['worst_problem'] == 5]),
       len(data['usability_events']),
       )
    if 'usability_events' in data:
        ret += "\n<ul>\n"
        for timestamp, event_data in data['usability_events'].items():
            ret += "<li><strong>%s</strong> (problem level %d):\n <ul>\n" % (timestamp, event_data['worst_problem'])
            try:
                for test in event_data['tests_failed']:
                    ret += "  <li>Failed test: %s (%s)</li>\n" % (test['test_failed'], "; ".join(["%s=%s" % (label, value) for label, value in test['relevant_data'].items()]))
            except BaseException:
                log_it("WARNING: apparently, no tests were failed here. What's going on?", 1)
            ret += " </ul>\n</li>\n"
        ret += "</ul>"
    return ret

def single_rule_description(test):
    """Given a TEST (a bit of executable code run over a ping transcript), return
    the source description of the test. Rather fragile and based on the facts
    of how I'm currently writing tests for this program.
    """
    return inspect.getsourcelines(test)[0][0].strip().lstrip(""""'test': """).rstrip(',"').strip()

def ping_rules_description():
    """Returns a description of the rules currently used to check ping transcripts."""
    ret = "<ul>\n%s\n</ul>" % '\n'.join([' <li>%s (level %s): <i><code>%s</code></i>.</li>' % (i['test_name'], i['problem_level'], single_rule_description(i['test'])) for i in usability_tests])
    ret += "\nAnother rule that is always applied: if <code>ping</code> fails with a DNS lookup failure (or for any other reason), this is considered to be a **level 5** usability event."
    return ret

def produce_daily_report(datafile):
    """Produces an HTML report summarizing the day's activity. Stores it in the
    appropriate part of the local filesystem.
    """
    with open(datafile, mode="rb") as data_store:
        daily_data = pickle.load(data_store)
    # date on which data was collected; overall summary; usability problem log, description of ping rules
    report = daily_report_template() % (os.path.basename(datafile).rstrip('.pkl'),
                                        daily_summary(daily_data),
                                        problem_log(daily_data),
                                        ping_rules_description(),
                                       )
    with open(os.path.join(reports_location, os.path.basename(datafile).rstrip('.pkl')+'.md'), mode="w") as output_file:
        output_file.write(report)


if __name__ == "__main__":
    # Run directly from the command line? Run through basic activities as a self-test.
    most_recent_report = sorted(glob.glob(os.path.join(data_location, "*pkl")))[-1]
    # most_recent_report = '/home/patrick/Documents/programming/python_projects/network-reporter/data/2017-12-26.pkl'
    produce_daily_report(most_recent_report)
