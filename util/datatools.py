# -*- coding: UTF-8 -*-
from __future__ import unicode_literals
__metaclass__ = type

import logging
import os
import json
from rdflib import Graph, URIRef, Namespace, RDF, RDFS, OWL


logger = logging.getLogger(__name__)

ID, TYPE, REV = '@id', '@type', '@reverse'


class Vocab:

    def __init__(self, vocab_source, vocab_uri, lang):
        self.index = {}
        label_key_items = []

        BASE_LABEL = URIRef(vocab_uri + 'label')
        g = Graph().parse(vocab_source, format='turtle')

        for s in set(g.subjects()):
            if not isinstance(s, URIRef):
                continue
            if not s.startswith(vocab_uri):
                continue

            key = s.replace(vocab_uri, '')

            label = key
            for label in g.objects(s, RDFS.label):
                if label.language == lang:
                    break
            if label:
                label = unicode(label)

            term = {ID: unicode(s),'label': label, 'curie': key}

            if (s, RDF.type, OWL.ObjectProperty) in g:
                term[TYPE] = ID

            self.index[key] = term

            label_distance = path_distance(g, s, RDFS.subPropertyOf, BASE_LABEL)
            if label_distance is not None:
                label_key_items.append((label_distance, key))

        self.label_keys = [key for ldist, key in sorted(label_key_items, reverse=True)]

    def sortedkeys(self, thing):
        def keykey(key):
            if key.startswith('@'):
                return (0, key)
            try:
                return (self.label_keys.index(key), key)
            except ValueError:
                weight = 200 if self.index[key].get(TYPE) == ID else 100
                return (weight, key)
        return sorted(thing, key=keykey)

    def labelgetter(self, item):
        for lkey in self.label_keys:
            label = item.get(lkey)
            if label:
                return label
        return item.get('@id')


def path_distance(g, s, p, base):
    """
    >>> ns = Namespace("urn:x-ns:")
    >>> g = Graph()
    >>> subpropof = RDFS.subPropertyOf
    >>> g.add((ns.name, subpropof, ns.label))
    >>> g.add((ns.title, subpropof, ns.name))
    >>> g.add((ns.notation, subpropof, ns.title))
    >>> g.add((ns.notation, subpropof, ns.name))

    >>> path_distance(g, ns.comment, subpropof, ns.label)
    >>> path_distance(g, ns.label, subpropof, ns.label)
    0
    >>> path_distance(g, ns.name, subpropof, ns.label)
    1
    >>> path_distance(g, ns.title, subpropof, ns.label)
    2
    >>> path_distance(g, ns.notation, subpropof, ns.label)
    2
    """
    if s == base:
        return 0
    def find_path(s, distance=1):
        shortest = None
        for o in g.objects(s, p):
            if o == base:
                return distance
            else:
                candidate = find_path(o, distance+1)
                if shortest is None or (candidate is not None
                        and candidate < shortest):
                    shortest = candidate
        return shortest
    return find_path(s)


class DB:

    def __init__(self, db_source, vocab):
        self.index = {}
        self.same_as = {}

        if not os.path.isfile(db_source):
            logger.warn("DB source %s does not exist", db_source)
            return

        for l in open(db_source):
            data = json.loads(l)
            data.pop('_marcUncompleted', None)
            item = data.pop('about')
            item['describedBy'] = data
            self.index[item[ID]] = item
            if 'sameAs' in item:
                for ref in item.get('sameAs'):
                    if ID in ref:
                        self.same_as[ref[ID]] = item[ID]

        chip_keys = [ID, TYPE] + vocab.label_keys
        for other in self.index.values():
            chip = {k: v for k, v in other.items() if k in chip_keys}
            for link, refs in other.items():
                if link == 'sameAs':
                    continue
                if not isinstance(refs, list):
                    refs = [refs]
                for ref in refs:
                    if not isinstance(ref, dict):
                        continue
                    ref_id = ref.get(ID)
                    if ref_id:
                        item = self.index.get(ref_id) or self.index.get(
                                self.same_as.get(ref_id))
                        if not item:
                            continue
                        item.setdefault(REV, {}
                                ).setdefault(link, []).append(chip)


if __name__ == '__main__':
    import doctest
    doctest.testmod()