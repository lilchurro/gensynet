#!/usr/bin/env python3
#
# Generate Synthetic Networks
# First Version: 8/3/2017
#
# An interactive script that generates a JSON file that can be used for
# creating imaginary (enterprise) network profiles
#
# INTERNAL USE ONLY; i.e., user input validation is nearly non-existent.
#
# Cyber Reboot
# alice@cyberreboot.org
#

import argparse
from datetime import datetime as dt
import ipaddress
import json
import math
from random import *
import string
import sys
import time
import uuid

VERBOSE = False
NET_SUMMARY = False
VERSION = '0.80'
DEBUG = True
OLDVERSION = False


def randstring(size):
    return ''.join(choice(string.ascii_lowercase + string.digits)
                    for _ in range(size))


def divide(dividend, divisor):
    quotient = math.floor(dividend/divisor)
    remainder = dividend % divisor
    return (quotient, remainder)

# you'll want to make sure that prefix is some string that
# is prefixed by some number.
def generate_ip(prefix, octets=4):
    ip = prefix
    if prefix[len(prefix)-1] is not '.':
        prefix = prefix + '.'
    subn = 4 - prefix.count('.')
    if (subn > 0):
        ip = prefix + '.'.join(str(randint(1,252)) for _ in range(subn))
    return ip


def generate_uuid():
    return str(uuid.uuid4())


def generate_fqdn(domain=None, subdomains=0):
    if domain is None:
        domain = randstring(randint(5,10)) + '.local'
    if subdomains == 0:
        return domain
    else:
        hostname = domain

    while (subdomains > 0):
        hostname = randstring(randint(3,5)) + '.' + hostname
        subdomains -= 1
    return hostname


def generate_os_type(devicetype):
    if ( devicetype == 'Business workstations'
      or devicetype == 'Developer workstations'
      or devicetype == 'Mail servers'
      or devicetype == 'File servers'
      or devicetype == 'Internal web servers'
      or devicetype == 'Database servers'
      or devicetype == 'Code repositories'
      or devicetype == 'SSH servers'):
        return choice(['Windows', 'Linux', 'Mac OS X', 'BSD'])
    elif devicetype == 'Smartphones':
        return choice(['iOS', 'Android', 'Blackberry', 'Unknown'])
    elif devicetype == 'DNS servers':
        return choice(['Windows', 'Linux', 'Mac OS X', 'BSD', 'Cisco IOS'])
    elif ( devicetype == 'Printers'
      or devicetype == 'PBXes'):
        return choice(['Linux', 'Unknown', 'Windows'])
    elif devicetype == 'DHCP servers':
        return choice(['Linux', 'Unknown', 'Windows', 'BSD', 'Cisco IOS'])
    elif devicetype == 'Active Directory controllers':
        return choice(['Unknown', 'Windows'])
    elif devicetype == 'VOIP phones':
        return choice(['Linux', 'Windows', 'Unknown'])
    elif devicetype == 'Unknown':
        return 'Unknown'
    return os


def generate_mac():
    mac = ':'.join(str(hex(randint(0,15))) + str(hex(randint(0,15)))
                   for _ in range(6))
    return mac.replace('0x', '')


def record(records=None):
    records = [ 'p0f',
                'nmap',
                'BCF']
    return choice(records)


def calculate_subnets(total, breakdown):
    """Returns number of subnets, given the breakdown; or -1 if breakdown doesn't work."""
    sanity_percent = 0 # if this isn't 100% by the end, we got issues.
    subnets = 0
    for nodep, netp in breakdown:
        sanity_percent += nodep
        if (sanity_percent > 100):
            return -1
        subtotal = int(total * .01 * nodep)
        groupby = int(254 * .01 *netp)
        subnets += math.ceil(subtotal/groupby)
    if (sanity_percent < 100):
        return -1
    return subnets


def get_default_dev_distro(nodect, printout=True):
    """Prints device type breakdowns using default ratios and returns a count of each device."""
    print("Default Device Role Distribution for {} nodes".format(nodect))
    dev_breakdown = {
        'Business workstations': int(math.floor(nodect*.35)),
        'Developer workstations': int(math.floor(nodect*.15)),
        'Smartphones': int(math.floor(nodect*.28)),
        'Printers': int(math.floor(nodect*.03)),
        'Mail servers': int(math.floor(nodect*.01)),
        'File servers': int(math.floor(nodect*.02)),
        'Internal web servers': int(math.floor(nodect*.06)),
        'Database servers': int(math.floor(nodect*.01)),
        'Code repositories': int(math.floor(nodect*.01)),
        'DNS servers': int(math.floor(nodect*.01)),
        'DHCP servers': int(math.floor(nodect*.01)),
        'Active Directory controllers': int(math.floor(nodect*.01)),
        'SSH servers': int(math.floor(nodect*.01)),
        'VOIP phones': 0,
        'PBXes': 0,
        'Unknown': int(math.floor(nodect*.04))
    }
                            # any nodes left over gets put into Unknown
    total = 0
    for key, ct in sorted(dev_breakdown.items()):
        if (printout and key != 'Unknown'):
            print("  {:>30} : {}".format(key, ct))
        total += ct
    if (nodect > total):
        dev_breakdown['Unknown'] += (nodect - total)
    if (printout):
        print("  {:>30} : {}".format('Unknown', dev_breakdown['Unknown']))

    return dev_breakdown


def build_configs(subnets, host_count, dev_div, domain=None):
    """Returns a json object of subnet specifications, or None upon error"""
    global VERBOSE
    jsons = []
    ip_addr = []
    roles = dict.fromkeys(dev_div.keys(), 0)

    ncount = 0

    if len(subnets)/254 > 254:
        print("WARNING: You're about to see some really sick IPs. Have fun.")

    for n in subnets:
        if VERBOSE:
            print("Building subnet {}:".format(ncount))
        addy = (randint(0,253), randint(0,253))
        while addy in ip_addr:
            addy = (randint(0,253), randint(0,253))
        ip_addr.append(addy)
        jsons.append({
                    "start_ip"  : '10.{}.{}.2'.format(addy[0],addy[1]),
                    "netmask"   : '10.{}.{}.0/24'.format(addy[0], addy[1]),
                    "hosts"     : n,
                    "roles"     : roles.copy()
                })
        if VERBOSE:
            print("start_ip: {}\t number of hosts: {}\t".format(jsons[-1]['start_ip'], jsons[-1]['hosts']))

    return jsons



def build_configs_deprecated(total, net_div, dev_div, domain=None):
    """Returns a json object of subnet specifications, or None upon error"""
    global VERBOSE
    total_subnets = calculate_subnets(total, net_div)
    if total_subnets < 1:
        if VERBOSE:
            print("WARNING: Could not break down nodes into the requested subnets.")
        return None

    jsons = []
    host_counter = []
    ncount = 0
    roles = dict.fromkeys(dev_div.keys(), 0)

    class_b,class_c = divide(total_subnets, 254)
    for n in net_div:
        if VERBOSE:
            ncount += 1
            print("Starting net_div {} of {}".format(ncount, len(net_div)))
        nodes = round(total * .01 * n[0])
        grouped_nodes = round(252 * .01 * n[1])
        q,r = divide(nodes, grouped_nodes)
        if class_b > 254:
            print("WARNING: You're about to see some really sick IPs. Have fun.")
        while q > 0:
            if class_c == 0:
                class_b -= 1
                class_c = 255
            class_c -= 1
            start_ip = '10.{}.{}.1'.format(class_b, class_c)
            netmask = '10.{}.{}.0/24'.format(class_b, class_c)
            jsons.append({
                        "start_ip"  : start_ip,
                        "netmask"   : netmask,
                        "hosts"     : grouped_nodes,
                        "roles"     : roles.copy()
                    })
            host_counter.append(grouped_nodes)
            if VERBOSE:
                print("Initialized subnet {} with {} hosts starting at {}".format(len(jsons), grouped_nodes, start_ip))
            q -= 1
        if r > 0:
            if class_c == 0:
                class_b -= 1
                class_c = 255
            class_c -= 1
            start_ip = '10.{}.{}.1'.format(class_b, class_c)
            netmask = '10.{}.{}.0/24'.format(class_b,class_c)
            jsons.append({
                        "start_ip"  : start_ip,
                        "netmask"   : netmask,
                        "hosts"     : r,
                        "roles"     : roles.copy()
                    })
            host_counter.append(r)
            if VERBOSE:
                print("Initialized subnet {} with {} hosts starting at {}".format(len(jsons), r, start_ip))
    if len(jsons) != total_subnets:
        print("BUG: Number of subnets created not equal to predicted {}".format(total_subnets))

    if DEBUG:
        print("DEBUG: host_counter = {}\ttotal subnets = {}".format(host_counter, total_subnets))

    total_hosts = 0
    for dev in dev_div:
        ct = dev_div[dev]
        total_hosts += ct
        if (DEBUG):
            print("DEBUG: dev = {}\tcount = {}\ttotal = {}\thost_counter = {}".format(dev, dev_div[dev], total_hosts, host_counter))
        while ct > 0:
            randomnet = randrange(0, total_subnets)
            if host_counter[randomnet] > 0:
                jsons[randomnet]['roles'][dev] += 1
                host_counter[randomnet] -= 1
                ct -= 1
    if total_hosts != total:
        print("BUG: Number of devices in breakdown did not add up to {}".format(total))

    return jsons


def randomize_subnet_breakdown(count, minimum, maximum):
    subnets = []
    nodes_left = count
    while (nodes_left > 0):
        clients = randint(minimum, maximum)
        subnets.append(clients)
        nodes_left -= clients
        if minimum < nodes_left < maximum:
            subnets.append(nodes_left)
            nodes_left = 0
    return subnets



def build_network(subnets, fname, randomspace=True, prettyprint=True):
    global VERBOSE
    ofile = open(fname, 'w')
    subnets_togo = len(subnets)
    ofile.write("[")
    for n in subnets:
        start_ip = ipaddress.ip_address(n['start_ip'])
        role_ct = dict(n['roles'])
        hosts_togo = n['hosts']
        ip_taken = []
        subnets_togo -= 1

        while (hosts_togo > 0):
            host = {
                'uid':generate_uuid(),
                'mac':generate_mac(),
                'rDNS_host':randstring(randrange(4,9)),
                'netmask':n['netmask']
            }

            if 'domain' in n:
                host['rDNS_domain'] = n['domain']

            host['record'] = {
                'source':record(),
                'timestamp': str(dt.now())
            }

            while True:
                a_role = choice(list(role_ct.keys()))
                if role_ct[a_role] > 0:
                    role_ct[a_role] -= 1
                    host['role'] = {
                        'role': a_role,
                        'confidence': randrange(55,100)
                    }
                    break
                else:
                    del(role_ct[a_role])

            host['os'] = { 'os': generate_os_type(host['role']['role']) }
            if host['os']['os'] != 'Unknown':
                host['os']['confidence'] = randrange(55,100)

            if (randomspace):
                while True:
                    ip = start_ip + randrange(0, 254)
                    if ip not in ip_taken:
                        host['IP'] = str(ip)
                        ip_taken.append(ip)
                        break
            else:
                ip = start_ip + hosts_togo
                host['IP'] = str(ip)

            if (prettyprint):
                if (subnets_togo > 0):
                    ofile.write("{},\n".format(json.dumps(host, indent=2)))
                else:
                    if (hosts_togo > 1):
                        ofile.write("{},\n".format(json.dumps(host, indent=2)))
                    else:
                        ofile.write("{}".format(json.dumps(host, indent=2)))
            else:
                ofile.write("{},\n".format(json.dumps(host)))

            hosts_togo -= 1

    ofile.write("]")
    ofile.close()


def main():
    global VERBOSE, VERSION, NET_SUMMARY, OLDVERSION
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', help='Provide program feedback', action="store_true")
    parser.add_argument('-s', '--summarize', help='Prints network configurations to output', action="store_true")
    parser.add_argument('-d', '--deprecate', help='Use the deprecated version for building subnets', action='store_true')
    parser.add_argument('--version', help='Prints version', action="store_true")
    args = parser.parse_args()
    if args.version:
        print("{} v{}".format(sys.argv[0], VERSION))
        sys.exit()
    if args.verbose:
        VERBOSE = True
    if args.summarize:
        NET_SUMMARY = True
    if args.deprecate:
        OLDVERSION = True

    outname = '{}.json'.format(time.strftime("%Y%m%d-%H%M%S"))

    print('\n\n\tSYNTHETIC NETWORK NODE GENERATOR\n')

    while True:
        nodect = int(input("How many network nodes? [500]: ") or "500")

        if nodect > 4000000:
            print("That ({}) is just exorbitant. Next time try less than {}.".format(nodect, 4000000))
            sys.exit()

                                #  setting subnet breakdown ----------------
        if OLDVERSION:
            if (nodect > 50):
                print('Default Node distribution of {} nodes across Class C subnets: '.format(nodect))
                print('   30% of the nodes will occupy subnets that are 70% populated')
                print('   45% of the nodes will occupy subnets that are 20% populated')
                print('   25% of the nodes will occupy subnets that are 90% populated')
                net_breakdown = [(30,70), (45,20), (25,90)]
                print('Total subnets: {}'.format(calculate_subnets(nodect, net_breakdown)))
                set_net = input("Manually set network node distribution? [No]: ") or "No"
            else:
                set_net = "No"
                net_breakdown = [(100, 100)]
                print('Total subnets: 1')

            if (set_net.lower() != 'no' and set_net.lower() != 'n'):
                net_breakdown = []
                percent = 100
                print("Please enter what percentage of the {} nodes would consume what percentage".format(nodect))
                print("of the Class C address space...")
                while percent > 0:
                    nodes = int(input("   Percent of nodes (MAX={}): ".format(percent)) or "100")
                    density = int(input("   Percent of class C space occupied: ") or "100")
                    if (nodes <= 100 and nodes > 1):
                        percent = percent - nodes
                    else:
                        print("Illegal node percentage value ({})".format(nodes))
                        continue
                    if (density > 100 or density < 1):
                        print("Illegal density percentage value ({})".format(density))
                        continue
                    net_breakdown.append((nodes, density))
                subnets = calculate_subnets(nodect, net_breakdown)
                print('Total subnets: {}'.format(subnets))
        else:
            MAX_max = MAX_min = -1
            while True:
                subnets = []
                if nodect <= 252:
                    subnets.append(nodect)
                else:
                    if MAX_max == -1:
                        MAX_max = 150
                    while True:
                        maximum = int(input('Max hosts in subnet (UP TO 252) [{}]: '.format(MAX_max)) or MAX_max)
                        if (maximum < 3 or maximum > 252):
                            print("Illegal 'maximum' value.")
                        else:
                            break

                    if MAX_min == -1 or maximum != MAX_max:
                        MAX_min = maximum-1 if (maximum-1 < nodect-maximum) else nodect-maximum
                    while True:
                        minimum = int(input('Min hosts in subnet (UP TO {}) [{}]: '.format(MAX_min, MAX_min)) or MAX_min)
                        if (minimum < 2 or minimum > MAX_min):
                            print("Illegal 'minimum' value.")
                        else:
                            break
                    MAX_min = minimum
                    MAX_max = maximum

                    subnets = randomize_subnet_breakdown(nodect, minimum, maximum)

                for i in [i for i,e in enumerate(subnets)]:
                    print('Subnet #{} has {} hosts.'.format(i, subnets[i]))

                subnets_finished = input("Is this breakout of subnets OK? [Yes]: ") or "Yes"
                if subnets_finished.lower() == 'yes' or subnets_finished.lower() == 'y':
                    break

                                #  setting device breakdown ----------------
        dev_breakdown = get_default_dev_distro(nodect)
        dev_distr = input("Manually reset the above Device Role Distribution? [No]: ") or "No"
        if (dev_distr.lower() != 'no' and dev_distr.lower() != 'n'):
            remainder = nodect
            for category in sorted(dev_breakdown.keys()):
                if (remainder == 0):
                    dev_breakdown[category] = 0
                    continue
                category_count = dev_breakdown[category]
                while (remainder > 0):
                    if (remainder < category_count):
                        category_count = remainder
                    category_count = int(input("   {} (MAX={}) [{}]: ".format(category, remainder, category_count)) or category_count)
                    remainder -= category_count
                    if (remainder < 0 or category_count < 0):
                        print("Illegal value '{}'".format(category_count))
                        remainder += category_count
                    else:
                        dev_breakdown[category] = category_count
                        break;
            if (remainder > 0):
                dev_breakdown['Unknown'] += remainder

        domain = input("Domain name to use (press ENTER to auto-generate): ") or generate_fqdn()
        cont = input("Ready to generate json (No to start over)? [Yes]: ") or "Yes"
        print("DEBUG: cont was given {}".format(cont))
        if cont.lower() == 'yes' or cont.lower() == 'y':
            break

    if OLDVERSION:
        net_configs = build_configs_deprecated(nodect, net_breakdown, dev_breakdown, domain)
    else:
        net_configs = build_configs(subnets, nodect, dev_breakdown, domain)
    if NET_SUMMARY or VERBOSE:
        print("\nBased on the following config:\n")
        print(json.dumps(net_configs, indent=4))
    #     print("\nSaved network profile to {}".format(outname))
    # else:
    #     print("\n Saved network profile to {}".format(outname))
    #build_network(net_configs, outname)



if __name__ == "__main__":
    main()
