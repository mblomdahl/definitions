import json
from urlparse import urljoin
from rdflib import *
from rdflib.namespace import *
from rdflib.util import guess_format
#from lxltools.graphcache import GraphCache, vocab_source_map


SDO = Namespace("http://schema.org/")
VANN = Namespace("http://purl.org/vocab/vann/")
VS = Namespace("http://www.w3.org/2003/06/sw-vocab-status/ns#")


BASE = "https://id.kb.se/"
TERMS = Namespace(BASE + "vocab/")
MARC = Namespace(BASE + "marc/")
DATASET_BASE = Namespace(BASE + "dataset/")
ENUM_BASEPATH = "/marc/"

SKIP = ('Other', 'Unspecified', 'Unknown')


def parse_marcframe(dataset, marcframe):

    for part in ['patterns', 'bib', 'auth', 'hold']:
        parse_resourcemap(dataset, part, marcframe)

        g = dataset.get_context(DATASET_BASE["marcframe/fields"])
        for tag, field in marcframe[part].items():
            if not isinstance(field, dict):
                continue
            marc_source = "%s/%s" % (part, tag)
            add_terms(g, marc_source, field)

    return g


def parse_resourcemap(dataset, part, marcframe):
    if part != 'bib':
        return # TODO

    basegroup_map = {}

    enumgraph = dataset.get_context(DATASET_BASE["marcframe/enums"])

    def parse_fixed(tag, link, baseclass, groupname):
        for basename, coldefs in marcframe[part][tag].items():
            if basename.startswith('TODO') or not basename[0].isupper():
                continue
            rclass = newclass(enumgraph, basename, baseclass, groupname)
            if isinstance(coldefs, unicode):
                continue
            for coldfn in coldefs.values():
                if coldfn.get('addLink') == link:
                    map_key = coldfn['tokenMap']
                    basegroup_map[map_key] = rclass, groupname

    parse_fixed('008', 'contentType', TERMS.CreativeWork, "content")
    parse_fixed('007', 'carrierType', TERMS.Product, "carrier")


    g = dataset.get_context(DATASET_BASE["marcframe/fixfields"])

    tokenmaps = reduce(lambda a, b: a.update(b) or a,
            (d for d in marcframe['tokenMaps'] if isinstance(d, dict)), {})
    for mapname, dfn in tokenmaps.items():
        if mapname == 'TypeOfRecordType':
            for name in dfn.values():
                if not name:
                    continue
                rtype = newclass(g, name, None, "typeOfRecord")
        if mapname == 'BibLevelType':
            for name in dfn.values():
                if not name:
                    continue
                if name.lower().endswith(('part', 'unit')):
                    base = TERMS.Part
                elif name in ('MonographItem',
                        'AdministrativePostForLicenseBoundElectronicResource'):
                    base = None
                else:
                    base = TERMS.Aggregate
                if base:
                    rtype = newclass(g, name, base, "bibLevel")
        else:
            basegroup = basegroup_map.get(mapname)

            if not basegroup:
                continue

            for enumref in dfn.values():
                if not enumref or enumref in SKIP or 'Obsolete' in enumref:
                    continue
                stype = newclass(enumgraph, enumref, *basegroup)



def add_terms(g, marc_source, dfn, parentdomain=None):

    for k, v in dfn.items():
        if k.startswith('_'):
            continue
        if not v:
            continue

        if k == 'defaults':
            for dp in v:
                newprop(g, dp, {RDF.Property})
            continue

        if k == 'match':
            for matchdfn in v:
                matchdfn = matchdfn.copy()
                matchdfn.update({dk: dfn[dk] for dk in dfn
                        if dk not in matchdfn
                        and dk != k})
                add_terms(g, marc_source, matchdfn, parentdomain)
            continue

        elif dfn.get('addLink') == True:
            continue # actual definition comes from a matching rule per above

        rtypes = {
            'property': {OWL.DatatypeProperty, OWL.FunctionalProperty},
            'addProperty': {OWL.DatatypeProperty},
            'link': {OWL.ObjectProperty, OWL.FunctionalProperty},
            'addLink': {OWL.ObjectProperty},
        }.get(k)

        is_link = ('link' in dfn or 'addLink' in dfn)

        key_is_property = k in ('property', 'addProperty')

        if key_is_property and is_link:
            domainname = dfn.get('resourceType')
            rangename = None
        else:
            domainname = parentdomain
            aboutEntity = dfn.get('aboutEntity')
            if dfn.get('about', "").startswith('_:'):
                domainname = None
            elif aboutEntity == '?record':
                domainname = 'Record'
            elif aboutEntity == '?instance' or (not aboutEntity and not parentdomain):
                if 'bib' in marc_source.lower():
                    domainname = 'CreativeWork'
            domainname = dfn.get('aboutType') or domainname
            rangename = dfn.get('resourceType')

        for classname in [domainname, rangename]:
            if classname:
                newclass(g, classname)

        marc_source_path = marc_source
        if k.startswith('$'):
            marc_source_path = "%s-%s" % (marc_source, k[1:])
        elif k.startswith('['):
            marc_source_path = marc_source + k
        elif k in ('i1', 'i2'):
            marc_source_path = "%s-%s" % (marc_source, k)

        if not rtypes:
            if not isinstance(v, list):
                v = [v]
            for subdfn in v:
                if isinstance(subdfn, dict):
                    if not rangename and \
                            'tokenTypeMap' in dfn or 'recTypeBibLevelMap' in dfn and \
                            k[0].isupper():
                        subdomainname = k
                    elif is_link and not key_is_property:
                        subdomainname = rangename
                    else:
                        subdomainname = None
                    if k.startswith('['):
                        subdomainname = parentdomain
                    add_terms(g, marc_source_path, subdfn, subdomainname)
            continue

        newprop(g, v, rtypes, domainname, rangename, marc_source_path)


def newclass(g, name, base=None, termgroup=None):
    if ' ' in name:
        rclass = g.resource(BNode())
        rclass.add(RDFS.label, Literal(name, lang='sv'))
    elif name.startswith(ENUM_BASEPATH):
        rclass = g.resource(URIRef(urljoin(BASE, name)))
    else:
        rclass = g.resource(URIRef(TERMS[name]))
    rclass.add(RDF.type, OWL.Class)
    if base:
        rclass.add(RDFS.subClassOf, base)
    if termgroup:
        rclass.add(VANN.termGroup, Literal(termgroup))#ENUM[termgroup])
    return rclass

def newprop(g, name, rtypes, domainname=None, rangename=None, marc_source=None):
    if not isinstance(name, basestring) or name[0] == '_' or name in ('@id', '@type'):
        return
    rprop = g.resource(URIRef(TERMS[name]))
    for rtype in rtypes:
        rprop.add(RDF.type, rtype)
    if domainname:
        rprop.add(SDO.domainIncludes, TERMS[domainname])
    if rangename:
        rprop.add(SDO.rangeIncludes, TERMS[rangename])
    if marc_source:
        rprop.add(SKOS.closeMatch, MARC[marc_source])
    return rprop


def add_equivalent(dataset, g, refgraph, refbase, termsgraph):
    for s in refgraph.subjects():
        if not s.startswith(refbase) or s == refbase:
            continue
        qname = refgraph.qname(s)
        if ':' in qname:
            qname = qname.split(':')[-1]
        term = TERMS[qname]
        if (term, None, s) not in termsgraph:
            if (term, RDF.type, OWL.Class) in dataset:
                rel = OWL.equivalentClass
            elif (term, None, None) in dataset:
                rel = OWL.equivalentProperty
            else:
                continue
            g.add((term, rel, s))


if __name__ == '__main__':
    import sys, os, glob
    args = sys.argv[1:]
    if '-g' in args:
        args.remove('-g')
        fmt = 'trig'
    else:
        fmt = 'turtle'
    source = args.pop(0)
    termspath = args.pop(0) if args else None

    dataset = ConjunctiveGraph()
    dataset.namespace_manager.bind("owl", OWL)
    dataset.namespace_manager.bind("skos", SKOS)
    dataset.namespace_manager.bind("sdo", SDO)
    dataset.namespace_manager.bind("", TERMS)

    with open(source) as fp:
        marcframe = json.load(fp)

    parse_marcframe(dataset, marcframe)

    termsgraph = ConjunctiveGraph()
    if termspath:
        termsgraph.parse(termspath, format=guess_format(termspath))

    #graphcache = GraphCache("cache/graph-cache")
    #
    #for vocab, url in termsgraph.subject_objects(OWL.imports):
    #    termsgraph.namespace_manager.bind("", vocab)
    #    try:
    #        refgraph = graphcache.load(vocab_source_map.get(str(url), url))
    #    except:
    #        pass #print "Failed to load:", url # TODO: this is a problem
    #    #print "loaded:", url, len(refgraph)
    #    destgraph = dataset.get_context(DATASET_BASE["ext?source=%s" % url])
    #    add_equivalent(dataset, destgraph, refgraph, url, termsgraph)

    if termsgraph:
        dataset -= termsgraph
        dataset.remove((None, VANN.termGroup, None))
        #dataset.namespace_manager = termsgraph.namespace_manager

        #for s in dataset.subjects():
        #    if (s, OWL.equivalentProperty|OWL.equivalentClass, None) not in termsgraph:
        #        dataset.add((s, VS.term_status, Literal("unmapped")))

    #for update_fpath in glob.glob(
    #        os.path.join(os.path.dirname(__file__), 'vocab-update-*.rq')):
    #    with open(update_fpath) as fp:
    #        dataset.update(fp.read())

    dataset.serialize(sys.stdout, format=fmt)
