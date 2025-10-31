# ifc2lbd - IFC to Linked Building Data python converter

Python implementation of IFC to ifcOWL/LBD converter.
Currently it covers "lite" version of ifcOWL which means that values in IFC step file are represented as literal (e.g. for GUID is direct string instead of pointing out to another triple GlobalUniqueID_IfcProduct(number))

## Components

1. `main.py` - just an entry point
2. `cli.py` - CLI app
3. `convert.py` - Converter options (spf load, or stream)
4. `ifc_options.py` - IFC utilities (load, stream, getting schemas for namespace (and for full ifcOWL in the future))

## Usage

I provided a few IFC files you can try right away (in `tes_files` folder).

### The most common
If you are using `PyPi` and `venv`, then I would suggest just add your IfcOpenShell to your virtual environment and run it with `python` like so: 
```bash
# Basic
python run src/main.py --inputs input.ifc --outputs output.ttl
# With some flags
python run src/main.py --inputs input.ifc --outputs output.ttl --verbose
```


### Single File Conversion (TTL output)
```bash
# Basic usage (loads to memory)
pixi run -e stable-conda python src/main.py --inputs input.ifc --outputs output.ttl

# With verbose logging (timestamps for each step)
pixi run -e stable-conda python src/main.py -i input.ifc -o output.ttl --verbose

# With streaming (for large files)
pixi run -e experimental-conda python src/main.py -i input.ifc -o output.ttl --stream

# All options together
pixi run -e experimental-conda python src/main.py -i input.ifc -o output.ttl -v -s
```

### Multiple Files Conversion (TRIG output)
**NOTE** - the TRIG is not there yet. 
```bash
# Multiple files (automatically uses TRIG format)
pixi run -e stable-conda python src/main.py \
  --inputs file1.ifc file2.ifc file3.ifc \
  --outputs file1.trig file2.trig file3.trig \
  --verbose

# With streaming for large files
pixi run -e experimental-conda python src/main.py \
  -i data/input/Duplex.ifc data/input/Girder.ifc data/input/Viadotto.ifc \
  -o data/output/Duplex.trig data/output/Girder.trig data/output/Viadotto.trig \
  -v -s
```

### Command Options
- `-i, --inputs`: Input IFC file(s) - at least one required
- `-o, --outputs`: Output file(s) - must match number of inputs
- `-v, --verbose`: Show timestamped progress for each step
- `-s, --stream`: Stream IFC files instead of loading to memory (useful for large files)

### Important Rules
- **Input/Output matching**: Number of inputs must equal number of outputs
- **Format selection**: 
  - Single file → TTL (Turtle) format
  - Multiple files → TRIG format (named graphs) (don't worry about it, it's not yet implemented)
- **Load vs Stream**:
  - Default: Load entire IFC to memory
  - `--stream`: Stream IFC file (good for large files, also fast - it requires Alpha version of IfcOpenShell from IfcOpenShell::IfcOpenShell conda channel)

### Get Help
```bash
pixi run -e stable-conda python src/main.py --help
```

## Output

### Verbose Mode Example
```
[2025-10-20 17:17:22.182] Starting IFC to LBD conversion
[2025-10-20 17:17:22.182] Processing 1 file(s)
[2025-10-20 17:17:22.183] Mode: Load to memory
[2025-10-20 17:17:22.183] [1/1] Converting 'input.ifc' -> 'output.ttl'
[2025-10-20 17:17:22.317] [1/1] Completed successfully
[2025-10-20 17:17:22.317] ==================================================
[2025-10-20 17:17:22.317] Conversion complete: 1/1 successful
```


## Development

It uses pixi manager (this way you can switch between pypi and conda version of IfcOpenshell).

### Environments
The project supports multiple pixi environments:

- **`stable-conda`**: Main development environment (recommended)
  - Stable ifcopenshell from conda
  - Full feature support including streaming
  - Use: `pixi run -e stable-conda ...`

- **`stable-pypi`**: Alternative stable environment
  - ifcopenshell from PyPI
  - Use: `pixi run -e stable-pypi ...`

- **`experimental-conda`**: Bleeding-edge features
  - Latest ifcopenshell with newest features
  - Use for testing new capabilities
  - Use: `pixi run -e experimental-conda ...`

- **`test`**: Testing environment
  - Includes pytest
  - Use: `pixi run -e test pytest`

### Short about environments.

**For conda developers**:`stable-conda`
It doesn't have `stream2` option yet - I'll keep an eye on this if it does)
```bash
pixi run -e stable-conda python src/main.py -i input.ifc -o output.ttl
```

**For streaming large files (and potentially faster conversion)**: `experimental-conda` with streaming flag (`--stream`).
So far streaming is only available in Alpha version of IfcOpenShell.
```bash
pixi run -e stable-conda python src/main.py -i large.ifc -o output.ttl -s -v
```

**For PyPi developers**: `stable-pypi`:
If someone uses IfcOpenShell from PyPi. Mind you, streaming `stream2` is not there yet.
```bash
pixi run -e experimental-conda python src/main.py -i input.ifc -o output.ttl
```

### Run Tests
```bash
pixi run -e test pytest
```

