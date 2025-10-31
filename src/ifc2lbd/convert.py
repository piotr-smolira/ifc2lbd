"""Core conversion logic from IFC to LBD Turtle format."""
import sys
from pathlib import Path
import time
import cProfile
import pstats
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent))

import ifcopenshell
from ifc.ifc_options import load_ifc, stream_ifc, get_schema_uri
from lbd.TTL_writer_strings_spf import string_writer_mini_ifcOWL, string_writer_ifcOWL
from lbd.TTL_writer_strings_stream import string_writer_mini_ifcOWL_stream, string_writer_ifcOWL_stream
# from lbd.ifcow_express_writer import string_writer_ifcowl_express  # 


# Map converter names to writer functions (for loaded models)
CONVERTERS = {
    "mini_ifcowl": string_writer_mini_ifcOWL,
    "ifcowl": string_writer_ifcOWL,
    # "ifcowl_express": string_writer_ifcowl_express,s
}

# Map converter names to streaming writer functions
STREAM_CONVERTERS = {
    "mini_ifcowl": string_writer_mini_ifcOWL_stream,
    "ifcowl": string_writer_ifcOWL_stream,
    # "ifcowl_express": Not yet implemented for streaming
}


def ifc_to_lbd_ttl(input_ifc_path: str, output_ttl_path: str, stream: bool = False, verbose: bool = False, profile: bool = False, converter: str = "mini_ifcowl") -> None:
    """
    Convert a single IFC file to LBD Turtle format.
    
    Args:
        input_ifc_path: Path to input IFC file
        output_ttl_path: Path to output TTL file
        stream: If True, stream the IFC file instead of loading to memory
        verbose: If True, print timing information
        profile: If True, run with cProfile and save stats
        converter: Which converter to use ('mini_ifcowl', 'ifcowl', 'mini_reference')
    """
    if stream and converter not in STREAM_CONVERTERS:
        raise ValueError(f"Streaming not yet implemented for converter '{converter}'. Available for streaming: {list(STREAM_CONVERTERS.keys())}")
    
    if not stream and converter not in CONVERTERS:
        raise ValueError(f"Unknown converter '{converter}'. Available: {list(CONVERTERS.keys())}")
    
    if profile:
        profiler = cProfile.Profile()
        profiler.enable()
    
    start_total = time.time()
    
    # Load or stream IFC model
    start_load = time.time()
    if stream:
        ifc_model_or_iterator, file_path = stream_ifc(input_ifc_path)
        # For streaming, we pass the file path to get schema
        schema_source = file_path if file_path else ifc_model_or_iterator
    else:
        ifc_model_or_iterator = load_ifc(input_ifc_path)
        schema_source = ifc_model_or_iterator
    
    load_time = time.time() - start_load
    if verbose:
        print(f"{'Streaming' if stream else 'Loading'} IFC: {load_time:.3f}s")
    
    # Choosing ontologies/namespaces to use
    mini_ifc_name = f"https://mini-ifc.ifc/{get_schema_uri(schema_source)}/#"
    namespaces = {
        "BASE": "http://example.org/base#",
        #"IFC": get_schema_uri(schema_source),
        "MINIIFC": mini_ifc_name,
        #"IFC": get_schema_uri(schema_source),
        "INST": "https://lbd-lbd.lbd/ifc/instances#",
        "LIST": "https://w3id.org/list#",
        "EXPRESS": "https://w3id.org/express#",
        "RDF": "http://www.w3.org/1999/02/22-rdf#",
        "XSD": "http://www.w3.org/2001/XMLSchema#",
        "OWL": "http://www.w3.org/2002/07/owl#"
    }
    
    
    # Writer just serializes what it's told
    start_write = time.time()
    if stream:
        writer_function = STREAM_CONVERTERS[converter]
        writer_function(input_ifc_path, output_ttl_path, namespaces)
    else:
        writer_function = CONVERTERS[converter]
        writer_function(ifc_model_or_iterator, output_ttl_path, namespaces)
    
    write_time = time.time() - start_write
    if verbose:
        print(f"Writing TTL: {write_time:.3f}s")
    
    total_time = time.time() - start_total
    if verbose:
        print(f"Total conversion: {total_time:.3f}s")
    
    if profile:
        profiler.disable()
        stats_file = output_ttl_path.replace('.ttl', '_profile.stats')
        profiler.dump_stats(stats_file)
        
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)
        print()
        print("="*80)
        print("TOP 20 FUNCTIONS BY CUMULATIVE TIME:")
        print("="*80)
        print(s.getvalue())
        print(f"Profile stats saved to: {stats_file}")
        print(f"To analyze: python -m pstats {stats_file}")


# Not there yet.
def ifc_to_lbd_trig(input_ifc_path: str, output_trig_path: str, stream: bool = False, verbose: bool = False, profile: bool = False, converter: str = "mini_ifcowl") -> None:
    """
    Convert a single IFC file to LBD (Linked Building Data) TriG format.
    Used when processing multiple files to keep each in separate named graphs.
    
    Args:
        input_ifc_path: Path to input IFC file
        output_trig_path: Path to output TRIG file
        stream: If True, stream the IFC file instead of loading to memory
        verbose: If True, print timing information
        profile: If True, run with cProfile and save stats
        converter: Which converter to use ('mini_ifcowl', 'ifcowl', 'mini_reference')
    """
    if converter not in CONVERTERS:
        raise ValueError(f"Unknown converter '{converter}'. Available: {list(CONVERTERS.keys())}")
    
    if stream:
        ifc_model = stream_ifc(input_ifc_path)
    else:
        ifc_model = load_ifc(input_ifc_path)
    
    namespaces = {
        "BASE": "http://example.org/base#",
        "IFC": get_schema_uri(ifc_model),
        "INST": "https://lbd-lbd.lbd/ifc/instances#",
        "LIST": "https://w3id.org/list#",
        "EXPRESS": "https://w3id.org/express#",
        "RDF": "http://www.w3.org/1999/02/22-rdf#",
        "XSD": "http://www.w3.org/2001/XMLSchema#",
        "OWL": "http://www.w3.org/2002/07/owl#"
    }
    
    file_name = Path(input_ifc_path).stem
    
    with open(output_trig_path, 'w', encoding='utf-8') as f:
        f.write("# LBD TriG output\n")
        f.write(f"# Converted from: {input_ifc_path}\n")
        f.write(f"# Mode: {'Streaming' if stream else 'Loaded to memory'}\n")
        f.write("\n")
        f.write("@prefix lbd: <https://w3id.org/lbd#> .\n")
        f.write("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n")
        f.write("\n")
        f.write(f"<http://example.org/graph/{file_name}> {{\n")
        f.write("    # TODO: Add actual conversion logic using string_writer_mini_ifcOWL\n")
        f.write("}\n")
