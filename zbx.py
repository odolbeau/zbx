#!/usr/bin/env python
"""Zabbix command ligne tools"""
# Usage: zbx.py
# Summary: Zabbix commands line interface
# Help: Commands for Zabbix
# Dude, Chick, Read the f****** README.md for dependancy and compliance !!

try:
    import configparser
except ImportError:
    import ConfigParser

import os
import re
import socket
import sys
import time
from datetime import datetime

# Find where the code is
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Force lib version embedded because tested or patched !
vendor_dir = os.path.join(BASE_DIR, 'vendor/python')
sys.path.insert(1, vendor_dir)

from pyzabbix import ZabbixAPI

from tabulate import tabulate

############################################
# Use for debug exchange with api
############################################
# import logging
# stream = logging.StreamHandler(sys.stdout)
# stream.setLevel(logging.DEBUG)
# log = logging.getLogger('pyzabbix')
# log.addHandler(stream)
# log.setLevel(logging.DEBUG)
############################################
# Use for debug step by step
############################################
# import pdb; pdb.set_trace()

# Import or use the embed version of fail with a correct warning msg
try:
    import click
except ImportError:
    sys.exit("""
You need Click! install it from https://github.com/pallets/click"
or run : sudo pip3 install click."
""")

# Import config file for zabbix API access
configfile = BASE_DIR + '/config.ini'
config = configparser.ConfigParser()
config.read(configfile)
ZABBIX_SERVER = config['zabbix']['server']
ZABBIX_USER = config['zabbix']['user']
ZABBIX_PASSWORD = config['zabbix']['password']

# Color stuff
eCOLOR_NONE = "\033[0;39m"
eLIGHT_RED = "\033[1;31m"
eLIGHT_GREEN = "\033[1;32m"
Bold = "\033[1m"
UnBold = "\033(B\033[m"

# Create connection to the zabbix api
zapi = ZabbixAPI(ZABBIX_SERVER)
zapi.login(ZABBIX_USER, ZABBIX_PASSWORD)

# use Click, a command line library for Python
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version='3.0.1')
def zabbix():
    """Zabbix user command line tools."""
    pass


@zabbix.group()
def maintenance():
    """Maintenance management sub-commands"""
    pass


@zabbix.group()
def host():
    """Host management sub-commands"""
    pass


@zabbix.group()
def group():
    """Group management sub-commands"""
    pass


@zabbix.group()
def monitor():
    """Monitore management sub-commands"""
    pass


@zabbix.group()
def alert():
    """Alert management sub-commands"""
    pass


##########################################################################
# FUNCTIONS
##########################################################################


def get_host_id(fqdn):
    """Get the host id."""
    response = zapi.host.get(
        output='extend',
        filter={"host": fqdn}
    )
    if not response:
        # click.echo('Host not found in Zabbix : %s' % fqdn)
        # sys.exit(42)
        return "not found"
    else:
        result = response[0]["hostid"]
        return result


def get_template_id(template_name):
    """Get the template id."""
    response = zapi.template.get(
        output='extend',
        filter={"host": "Template OS Linux"}
    )
    if not response:
        # click.echo('Template not found in Zabbix : %s' % template_name)
        # sys.exit(42)
        return "not found"
    else:
        result = response[0]["templateid"]
        return result


def get_group_id(group_name):
    """Get the group id."""
    response = zapi.hostgroup.get(
        output='extend',
        filter={"name": group_name}
    )
    if not response:
        # click.echo('Group Name not found in Zabbix : %s' % group_name)
        # sys.exit(42)
        return "not found"
    else:
        result = response[0]["groupid"]
        return result


def to_date(ts):
    """Humane date format."""
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')


def get_maintenance_id(host_id, fqdn):
    """Gate the maintenance id."""
    response = zapi.maintenance.get(
        output='extend',
        selectHosts='refer',
        selectGroups='refer',
        hostids=host_id
    )
    if not response:
        return "not found"
    elif response[0]["name"] != fqdn:
        return "generic maintenance: " + response[0]["name"]
    else:
        result = response[0]["maintenanceid"]
        return result


def delete_maintenance(maintenance_id):
    """Delete the maintenance."""
    response = zapi.maintenance.delete(maintenance_id,)
    if not response:
        return "not found"
    else:
        result = response["maintenanceids"]
        return result


def add_maintenance(host_id, duration, fqdn):
    """Add a maintenance."""
    # start maintenance 5 minutes before now to avoid overlapping
    start = int(time.time()) - 300
    end = start + int(duration) + 300
    response = zapi.maintenance.create(
        groupids=["5"],
        hostids=[host_id],
        name="Scripted Maintenance: %s" % fqdn,
        maintenance_type=0,
        description="zbx scripted",
        active_since=start,
        active_till=end,
        timeperiods=[{"timeperiod_type": 0,
                      "start_date": start,
                      "period": duration
                      }],
    )
    result = response["maintenanceids"]
    return result


def get_event(eventid):
    """Get eventid"""
    response = zapi.event.get(
        eventids=eventid,
        output="extend",
        select_acknowledges="extend",
    )
    return response[0]


##########################################################################
# Maintenance sub command
##########################################################################


@maintenance.command("list")
def list_maintenance():
    """List all maintenance currently set in the zabbix server"""
    response = zapi.maintenance.get(
        output='extend',
        selectGroups='extend',
        selectTimeperiods='extend',
    )
    tableau_maintenance = []
    for m in response:
        tableau_maintenance.append([
            m["name"], m["description"],
            to_date(m["active_since"]), to_date(m["active_till"])
        ])
    header = [Bold + "NAME", "DESCRIPTION", "ACTIVE SINCE", "ACTIVE UNTIL" + UnBold]
    print(tabulate(tableau_maintenance, headers=header, tablefmt="plain"))


@maintenance.command("add")
@click.argument('fqdn')
@click.argument('duration', default=3600)
def create_a_maintenance(fqdn, duration):
    """Add a maintenance for the host specified."""
    host_id = get_host_id(fqdn)
    if host_id == "not found":
        click.echo('Host not found in Zabbix : %s' % fqdn)
        sys.exit(42)
    else:
        maintenance_id = get_maintenance_id(host_id, fqdn)
        if maintenance_id == "not found":
            click.echo('Adding maintenance for %s during %s secondes' % (fqdn, duration))
            response = add_maintenance(host_id, duration, fqdn)
            click.echo('Maintenance id %s for %s added' % (response, fqdn))
        else:
            click.echo('Sorry maintenance already existe for %s ' % (fqdn))
            if "generic maintenance:" in maintenance_id:
                click.echo('%s is in %s' % (fqdn, maintenance_id))
            else:
                response = zapi.maintenance.get(
                    output='extend',
                    selectHosts='refer',
                    selectGroups='refer',
                    maintenanceids=maintenance_id
                )
                now = int(time.time())
                duration_plan = int(duration + now)
                if int(response['active_till']) < duration_plan:
                    click.echo('update')
                else:
                    click.echo('no update')


@maintenance.command("del")
@click.argument('fqdn')
def delete_a_maintenance(fqdn):
    """Remove a maintenance for the host specified."""
    host_id = get_host_id(fqdn)
    if host_id == "not found":
        click.echo('Host not found in Zabbix : %s' % fqdn)
        sys.exit(42)
    else:
        maintenance_id = get_maintenance_id(host_id, fqdn)
        if maintenance_id == "not found":
            click.echo('Maintenance not found in Zabbix')
            sys.exit(42)
        else:
            response = delete_maintenance(maintenance_id)
            click.echo('Maintenance id %s for %s removed' % (response, fqdn))


@maintenance.command()
def gc():
    """Maintenance garbage collector : remove all expired maintenance."""
    response = zapi.maintenance.get(
        output='extend',
        selectGroups='extend',
        selectTimeperiods='extend',
    )
    to_remove = []
    for maintenance in response:
        now = int(time.time())
        if int(maintenance['active_till']) < now:
            to_remove.append(maintenance)
    if len(to_remove) != 0:
        for m in to_remove:
            deleted = delete_maintenance(m['maintenanceid'])
            if deleted == "not found":
                click.echo('Maintenance %s not found' % m['name'])
            else:
                click.echo('Removing expired %s' % m['name'])
    else:
        click.echo('No expired maintenance to remove')


##########################################################################
# Host COMMANDS
##########################################################################


@host.command("add")
@click.argument('fqdn')
def create_a_host(fqdn):
    """Create a host in zabbix server."""
    template_os_linux = get_template_id("Template OS Linux")
    if template_os_linux == "not found":
        click.echo('template not found in Zabbix : %s' % template_os_linux)
        sys.exit(42)
    else:
        dns_data = socket.gethostbyname_ex(fqdn)
        ip = dns_data[2][0]
        response = zapi.host.create(
            host=fqdn,
            interfaces={"type": 1, "main": 1, "useip": 0, "ip": ip, "dns": fqdn, "port": "10050"},
            groups={"groupid": "5"},
            templates={"templateid": template_os_linux}
        )
        click.echo('%s id %s is added with basic linux template' % (fqdn, response["hostids"][0]))


@host.command("del")
@click.argument('fqdn')
def delete_a_host(fqdn):
    """Delete a host in zabbix server."""
    host_id = get_host_id(fqdn)
    if host_id == "not found":
        click.echo('Host not found in Zabbix : %s' % fqdn)
        sys.exit(42)
    else:
        response = zapi.host.delete(host_id)
        click.echo('%s id %s is removed of the zabbix server' % (fqdn, response["hostids"][0]))


@host.command("notemplate")
def get_list_server_without_template():
    """List all serveur without template."""
    tableau_server_without_template = []
    response = zapi.host.get(
        output="extend",
        selectParentTemplates=["templateid", "name"],
        selectGroups="extend",
    )
    click.secho("-- Host without template --", bold=True)
    for h in response:
        if len(h['parentTemplates']) == 0:
            tableau_server_without_template.append([h["name"], "without template"])
    print(tabulate(tableau_server_without_template, tablefmt="plain"))

##########################################################################
# Group COMMANDS
##########################################################################


@group.command("list")
@click.argument('group_name')
def list_server_in_group(group_name):
    """List server in groupe name."""
    group_id = get_group_id(group_name)
    if group_id == "not found":
        click.echo('Group not found in Zabbix : %s' % group_id)
        sys.exit(42)
    else:
        tableau_server_in_group = []
        list_servers = zapi.host.get(
            output='extend',
            groupids=group_id,
        )
        for host in list_servers:
            tableau_server_in_group.append([host["name"], group_name])
        header = [Bold + "NAME", "GROUP" + UnBold]
        print(tabulate(tableau_server_in_group, headers=header, tablefmt="plain"))

##########################################################################
# Monitor COMMANDS
##########################################################################


@monitor.command()
@click.argument('fqdn')
def enable(fqdn):
    """Enable monitoring for a host."""
    host_id = get_host_id(fqdn)
    if host_id == "not found":
        click.echo('Host not found in Zabbix : %s' % fqdn)
        sys.exit(42)
    else:
        # enable is status = 0
        response = zapi.host.update(
            hostid=host_id,
            status=0
        )
        click.echo('%s id %s is monitored now' % (fqdn, response["hostids"]))


@monitor.command()
@click.argument('fqdn')
def disable(fqdn):
    """Disable monitoring for a host."""
    host_id = get_host_id(fqdn)
    response = zapi.host.update(
        hostid=host_id,
        status=1
    )
    click.echo('%s id %s is not monitored now' % (fqdn, response["hostids"]))


##########################################################################
# Alert COMMANDS
##########################################################################


@alert.command("list")
@click.argument('nb', default=200)
def list_alert(nb):
    """List the last N alert (200 by default).

    With all that in "warning" or supperior in red
    if no maintenance is configured or acknowledgement envoy
    """
    int_nb = int(nb)
    tableau_alerte = []
    triggers = zapi.trigger.get(limite=int_nb,
                                selectLastEvent='extend',
                                selectGroups='extend',
                                selectHosts='extend',
                                monitored=1,
                                skipDependent=1,
                                output='extend',
                                expandDescription=1,
                                expandData='host',
                                sortfield='lastchange',
                                sortorder='DESC',
                                filter={"priority": [2, 3, 4, 5], "value": 1}
                                )

    for t in triggers:
        event_id = '-'
        ack = '-'
        maintenance = '-'
        last_date = datetime.fromtimestamp(int(t['lastchange'])).strftime('%Y-%m-%d %H:%M:%S')
        if t['lastEvent']:
            event_id = t['lastEvent']['eventid']
            event = zapi.event.get(eventids=event_id,
                                   select_acknowledges='extend',
                                   output='extend')
            if event[0]['acknowledges']:
                ack_by = event[0]["acknowledges"][0]["alias"]
                clean_ack_description = re.sub('----\[BULK ACKNOWLEDGE\]----', r'', event[0]['acknowledges'][0]['message'])
                ack = ack_by + " " + clean_ack_description
        if t["hosts"][0]["maintenance_status"] == "1":
            maintenance = "Main.."
        if int(t['priority']) >= 3 and maintenance != "Main.." and not event[0]['acknowledges']:
            alert = [eLIGHT_RED + t['hosts'][0]['name'], last_date, event_id, t["description"], maintenance, ack + eCOLOR_NONE]
        else:
            alert = [t['hosts'][0]['name'], last_date, event_id, t["description"], maintenance, ack]
        tableau_alerte.append(alert)
    header = [Bold + "Host", "Last Event", "Event Id", "Description", "Maintenance", "Acknowledge" + UnBold]
    print(tabulate(tableau_alerte, headers=header, tablefmt="plain"))


@alert.command("history")
@click.argument('days', default=1)
def history_alerts(days):
    """Alert history for last 24h or for n x 24h,"""
    now = int(time.time())
    n_day = int(days)
    secondes = (86400 * n_day)
    time_from = now - secondes
    history = zapi.alert.get(
        userids=9,
        output="extend",
        sortfield="alertid",
        sortorder="DESC",
        time_from=time_from,
    )
    unique = {each['eventid']: each for each in history}.values()
    tableau_history = []
    for alert in unique:
        event = get_event(alert["eventid"])
        host, subject = alert["subject"].split(':', 1)

        acked = "No"
        if event["acknowledged"] == "1":
            acked = "Yes"

        ack_by = ""
        if len(event["acknowledges"]) > 0:
            ack_by = event["acknowledges"][0]["alias"]

        tableau_history.append([
            event["eventid"],
            to_date(alert["clock"]),
            host,
            subject,
            acked,
            ack_by
        ])
    tableau_history = sorted(tableau_history, reverse=True)
    headers = ["Event ID", "Time", "Host", "Subject", "Acked", "Acked by"]
    print(tabulate(tableau_history, headers=headers, tablefmt="plain"))


@alert.command()
@click.argument('event_id')
@click.argument('message')
def ack(event_id, message):
    """Acknowledge a alert."""
    response = zapi.event.acknowledge(
        eventids=event_id,
        message=message,
    )
    click.echo('Alert event %s is acknowledged' % response["eventids"])


##########################################################################
# zbx general COMMANDS
##########################################################################


@zabbix.command()
def unmonitored():
    """List all host set in zabbix but not monitored (Disabled)"""
    tableau_unmonitored = []
    unmonitored = zapi.host.get(
        output='extend',
        filter={"status": 1}
    )
    for host in unmonitored:
        tableau_unmonitored.append([host["name"], "Not monitored"])
    header = [Bold + "NAME", "STATUS" + UnBold]
    print(tabulate(tableau_unmonitored, headers=header, tablefmt="plain"))


# MAIN
if __name__ == '__main__':
    zabbix()
