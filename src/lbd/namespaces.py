"""Namespace configuration for LBD/IFC conversion."""

from ifc.ifc_options import get_schema_uri


def get_namespaces(schema_source) -> dict[str, str]:
    """
    Get the standard namespaces for IFC to LBD conversion.
    
    Args:
        schema_source: An IFC model or file path to extract the schema URI from
        
    Returns:
        Dictionary mapping namespace prefixes to URIs
    """
    mini_ifc_name = f"https://mini-ifc.ifc/{get_schema_uri(schema_source)}/#"
    
    return {
        "BASE": "http://example.org/base#",
        "mifc": mini_ifc_name,
        "inst": "https://lbd-lbd.lbd/ifc/instances#",
        "rdf": "https://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "owl": "http://www.w3.org/2002/07/owl#"
    }


# Left out for now. It is only for full ifcOWL
# "LIST": "https://w3id.org/list#",
# "EXPRESS": "https://w3id.org/express#",
