from poll_emic.apiwrapper import *
from collections import Counter
from itertools import chain
from pprint import pprint as pp
from poll_emic.utils import call_api
import networkx as nx
import sys
import geopy

def get_mention_counts(user):

    pp("Getting mention counts for %s" % user)

    try:
        tweets = use_statuses_api(user)

        mentions = [tweet['entities']['user_mentions']
                    for tweet in tweets if tweet.get('retweeted_status') is None]
    
        counts = Counter([user['screen_name']
                          for user in chain.from_iterable(mentions)])
    except:
        print("Statuses response for %s was %s" % (user,tweets))

        counts = Counter()

    return counts

def get_mention_data(user,data):
    data['edges'][user] = get_mention_counts(user)


def get_mentionball(ego, data):

    get_mention_data(ego,data)

    for user in data['edges'][ego].keys():
        if data['edges'].get(user) is None:
            get_mention_data(user,data)

    return data


def data_to_network(data):
    G = nx.DiGraph()

    for fromu in data['edges'].keys():
        for tou in data['edges'][fromu].keys():
            G.add_edge(fromu,tou,weight=data['edges'][fromu][tou])

    return G

def lookup_metadata(data, graph):
    pp('Collecting lookup metadata')
    data['nodes'] = lookup_many(graph.nodes())
    pp("Has metadata for %d users" % len(data['nodes'].items()))

    geo = geopy.geocoders.ArcGIS()

    ucount = 0
    for user in graph.nodes():
        ucount += 1
        pp('%d of %d - Adding node attributes for %s' % (ucount, len(data['nodes'].items()), user))

        try:
            graph.node[user]['followers_count'] = data['nodes'][user]['followers_count']
            if 'location' in data['nodes'][user].keys() and data['nodes'][user]['location']!='':
                #pp(data['nodes'][user])
                location = data['nodes'][user]['location']
                # TODO: clean location of unicode characters, in particular u'\xdcT' (U[umlaut]T)
                # TODO: deal with cases with lat/long preceded by a string, e.g. "iPhone: -37.11111, 100.000000"
                try:
                    loc_string, (lat, long) =  geo.geocode(location)
                    graph.node[user]['loc_string'] = loc_string
                    graph.node[user]['loc_lat'] = lat
                    graph.node[user]['loc_long'] = long
                except geopy.exc.GeocoderTimedOut as e:
                    pp(data['nodes'][user]['location'])
                    graph.node[user]['loc_string'] = ''
                    graph.node[user]['loc_lat'] = ''
                    graph.node[user]['loc_long'] = ''
            else:
                graph.node[user]['loc_string'] = ''
                graph.node[user]['loc_lat'] = ''
                graph.node[user]['loc_long'] = ''
        except TwitterHTTPError as e:
            print e
            pp("Removing %s" % user)
            graph.remove_node(user)
        except KeyError as e:
            pp(lookup(user))
            print e
        except TypeError as e:
            pp(data['nodes'][user]['location'])
        except UnicodeEncodeError as e:
            pp(data['nodes'][user]['location'])

def clean_ball(graph):
    for user in graph.nodes():
        if (len(graph.predecessors(user)) < 2 and
            len(graph.neighbors(user)) < 1):
            graph.remove_node(user)

def get_members_from_list(owner,slug):
    users = call_api(twitter.lists.members,
                     {'owner_screen_name':owner,'slug':slug})['users']

    return [user['screen_name'] for user in users]

def main(args):

    egos = []

    for arg in args:
        # to do: deal with hashtags here
        if arg[0] is '@':
            if "/" in arg:
                parts = arg.split("/")
                egos.extend(get_members_from_list(parts[0][1:],parts[1]))
            else:
                egos.append(arg[1:])

    
    # replace egos with 

    data = {'nodes': {}, 'edges': {}}

    for ego in egos:
        data = get_mentionball(ego,data)

    G = data_to_network(data)
    lookup_metadata(data, G)

    clean_ball(G)

    nx.write_gexf(G,"mentionball-%s.gexf" % "+".join(args).replace('/','~'))

    print("Data: ")
    pp(data)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1:])
    else:
        print "Please include a screen name or user ID for ego as argument."

