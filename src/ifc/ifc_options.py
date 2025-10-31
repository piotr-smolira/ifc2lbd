import ifcopenshell

def load_ifc(file_path):
    """Loads an IFC in memory (standard SPF)"""
    model = ifcopenshell.open(file_path)
    return model

def stream_ifc(file_path):
    """
    Streams an IFC file (memory efficient, for large files).
    Note: Streaming is only available in ifcopenshell experimental versions.
    Falls back to loading if streaming is not available.
    
    Returns:
        tuple: (iterator/model, file_path) - file_path is included for schema detection
    """
    # Check if streaming is available (only in experimental versions, i.e. from Alpha IfcOpenShell)

    if hasattr(ifcopenshell, 'stream2'):
        return (ifcopenshell.stream2(file_path), file_path)
    else:
        # Streaming not available in stable versions, fall back to loading
        import warnings
        warnings.warn(
            "Streaming is not available in this ifcopenshell version. "
            "Falling back to loading entire file to memory. "
            "Use experimental-conda environment for streaming support.",
            UserWarning
        )
        return (load_ifc(file_path), None)


def get_schema_uri(ifc_model_or_path) -> str:
    """
    ifcOWL prefixes and URIs. For now, ifcOWL is not there yet, hence URI is custom for now.
    
    Args:
        ifc_model_or_path: IfcOpenShell model or file path (for streamed files)
        
    Returns:
        Schema version URI string for ifcOWL ontology
    """
    
    # Determine if it's a file path or loaded model
    if isinstance(ifc_model_or_path, str):
        # It's a file path - use stream2 to get schema from header entities
        schema = None
        if hasattr(ifcopenshell, 'stream2'):
            # Use stream2 to read header entities (includes file_schema)
            for entity_dict in ifcopenshell.stream2(ifc_model_or_path):
                if entity_dict.get('type') == 'file_schema':
                    schema = entity_dict.get('schema_identifiers', [None])[0]
                    break
        
        if not schema:
            # Fallback if stream2 not available or schema not found
            schema = 'IFC4'
    else:
        # It's a loaded model - use schema_identifier to get full version
        schema = ifc_model_or_path.schema_identifier
    
    # Map schema identifiers to OWL URIs
    schema_map = {
        'IFC2X3': 'https://standards.buildingsmart.org/IFC/DEV/IFC2x3/TC1/OWL#',
        'IFC4': 'https://standards.buildingsmart.org/IFC/DEV/IFC4/ADD2/OWL#',
        #IFC4X3 not official in buildingSMART
        'IFC4X3': 'https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#',
        'IFC4X3_ADD2': 'https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#',
    }
    return schema
    #return schema_map.get(schema.upper(), f'https://standards.buildingsmart.org/IFC/DEV/{schema}/OWL#')