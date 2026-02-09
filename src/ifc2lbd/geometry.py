from collections import defaultdict
import itertools
import re
import toposort
import rdflib
import ifcopenshell.geom

num_regexp = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
wkt_lit = rdflib.term.URIRef('http://www.opengis.net/ont/geosparql#wktLiteral')

class geometry_processor:

    def __init__(self, f):
        self.file = f
        self.graph = None
        self.obsolete_instances = []
        self.guid_to_uri = defaultdict(list)

    def process(self, base=None):
        buff = ifcopenshell.geom.serializers.buffer()
        sett = ifcopenshell.geom.settings()
        sett.set('triangulation-type', ifcopenshell.ifcopenshell_wrapper.POLYHEDRON_WITH_HOLES)
        sett.set('use-world-coords', True)
        sett.set('dimensionality', ifcopenshell.ifcopenshell_wrapper.CURVES_SURFACES_AND_SOLIDS)
        ssett = ifcopenshell.geom.serializer_settings()
        if base:
            ssett.set('base-uri', base)
        sr = ifcopenshell.geom.serializers.ttl(buff, sett, ssett)
        sr.writeHeader()
        all_geometry = set()

        # we don't care about type geometry, clean it up so that it doesn't retain shape representations
        for ty in self.file.by_type('IfcTypeProduct'):
            for rmap in ty.RepresentationMaps:
                all_geometry.update(filter(lambda i: i.is_entity(), self.file.traverse(rmap)))
            ty.RepresentationMaps = None

        for proddef in self.file.by_type('ifcproductdefinitionshape'):
            for prod_rep in itertools.product(proddef.ShapeOfProduct, proddef.Representations):
                shp = ifcopenshell.geom.create_shape(sett, *prod_rep)
                sr.write(shp)
            all_geometry.update(filter(lambda i: i.is_entity(), self.file.traverse(proddef)))
            # Set to None so that we have no in-edges
            for prod in proddef.ShapeOfProduct:
                prod.Representation = None

        dependencies = {
            inst.id(): [i.id() for i in self.file.traverse(inst, max_levels=1)[1:] if i.is_entity()]
            for inst in all_geometry
        }

        # convert to ids so that we do not refer to deleted data by accident
        all_geometry = {i.id() for i in all_geometry}

        geometry_topo_order = toposort.toposort_flatten(dependencies)
        for inst in map(self.file.__getitem__, geometry_topo_order):
            # all in edges are in our deleted
            if {i.id() for i in self.file.get_inverse(inst)} <= all_geometry:
                self.obsolete_instances.append(inst)

        del sr
        self.graph = rdflib.Graph()
        self.graph.parse(data=buff.get_value(), format="ttl")

        for feat in (r[0] for r in self.graph.query('''select ?s where { ?s a <http://www.opengis.net/ont/geosparql#Feature> }''')):
            guid = ifcopenshell.guid.compress(''.join(feat.rsplit('/', 1)[1].split('_')[1:-1]))
            self.guid_to_uri[guid].append(feat)

    def remove_from_file(self):
        for inst in self.obsolete_instances:
            self.file.remove(inst)

    def lookup(self, inst, subject, namespaces={}):
        # a bit wasteful; used in fmt() below
        G = rdflib.Graph()
        for prefix, iri in namespaces.items():
            G.bind(prefix, iri, override=True)

        def bfs(start):
            stack = [start]
            visited_nodes = set()

            while stack:
                s = stack.pop()
                if s in visited_nodes:
                    continue
                visited_nodes.add(s)

                for p, o in self.graph.predicate_objects(s):
                    if p in (rdflib.namespace.RDFS.label, rdflib.namespace.DCTERMS.identifier):
                        continue
                    if "body_footprint_geometry" in o:
                        # @nb this is calculated in the serializer, not actually in the model, skip these
                        continue

                    def round_wkt_lit(lit, ndigits: int = 6):
                        if isinstance(lit, rdflib.Literal) and lit.datatype == wkt_lit:
                            def repl(m: re.Match) -> str:
                                v = round(float(m.group()), ndigits)
                                s = f"{v:.{ndigits}f}".rstrip("0").rstrip(".")
                                return "0" if s in {"", "-0"} else s

                            return type(lit)(
                                num_regexp.sub(repl, str(lit)),
                                datatype=lit.datatype,
                                lang=lit.language,
                            )
                        return lit

                    yield (s, p, round_wkt_lit(o))

                    # Recurse only into resource nodes (not literals)
                    if isinstance(o, (rdflib.URIRef, rdflib.BNode)):
                        stack.append(o)

        def fmt(v):
            # @todo not complete, no escaping, etc.
            if isinstance(v, rdflib.URIRef):
                if v == rdflib.namespace.RDF.type:
                    return 'a'
                else:
                    for k, n in namespaces.items():
                        if v.startswith(n):
                            return f'{k}:{str(v)[len(n):]}'
                return f'<{v}>'
            else:
                return v.n3(G.namespace_manager)

        if g := getattr(inst, 'GlobalId', None):
            for s in self.guid_to_uri.get(g, ()):
                yield from ((subject if _s == s else fmt(_s), fmt(_p), fmt(_o)) for _s, _p, _o in bfs(s))
