# SMRX: Smart Regex Engine

**SMRX** is a high-performance, cached regex engine built into Naze for fast, intelligent file searching and pattern matching across large codebases.

## Features

- **Fast Pattern Matching**: Compiled pattern caching for rapid regex execution
- **File-Level Caching**: Cache match results for frequently searched files
- **Binary File Detection**: Automatically skips binary files during searches
- **Memory Efficient**: Configurable cache sizes to balance speed and memory
- **Batch Processing**: Search multiple files with a single operation
- **Group Extraction**: Extract capture groups from matches
- **Pattern Replacement**: Replace matches with substitutions
- **Pattern Validation**: Pre-compile patterns for error detection
- **Streaming Results**: Handle large result sets efficiently

## CLI Usage

### Basic Regex Search

```bash
# Search for function definitions
python main.py regex-search 'def\s+\w+\(' --files '*.py'

# Search for email addresses
python main.py regex-search '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Case-insensitive hex color search
python main.py regex-search '#[0-9a-f]{6}' -f '*.html'
```

### Options

- `--files`, `-f`: File pattern to search (default: `*`)
- Pattern is case-insensitive by default

## Chat Mode Usage

Use natural language to trigger regex searches:

```
> search regex def\s+\w+\(
> find with regex [0-9]{3}-[0-9]{4}
> regex search email@pattern
```

## Python API

### Quick Text Search

```python
import smrx

# Find all matches in a string
text = "The quick brown fox jumps over the lazy dog"
matches = smrx.quick_search(text, r'\b\w{4,}\b')
# [{'match': 'quick', 'start': 4, 'end': 9, 'groups': None}, ...]
```

### Directory Search

```python
import smrx

# Search files in directory
result = smrx.search(
    directory='/path/to/code',
    regex_str=r'TODO:.*',
    file_pattern='*.py',
    recursive=True,
    case_sensitive=False,
    max_results=1000
)

print(f"Found {result.matches_found} matches in {result.total_files_searched} files")
print(f"Execution time: {result.execution_time:.3f}s")

for match in result.matches[:10]:
    print(f"{match.filepath}:{match.line_num}:{match.col_num}")
    print(f"  {match.line_text}")
    print(f"  Match: {match.match_text}")
```

### Pattern Validation

```python
import smrx

# Check if pattern is valid
is_valid, error = smrx.validate(r'[unclosed')
if not is_valid:
    print(f"Invalid pattern: {error}")
```

### Extract Groups

```python
import smrx

text = "John: 25, Jane: 30, Bob: 35"

# Extract names (group 1)
names = smrx.extract(text, r'(\w+):\s+(\d+)', group=1)
# ['John', 'Jane', 'Bob']

# Extract ages (group 2)
ages = smrx.extract(text, r'(\w+):\s+(\d+)', group=2)
# ['25', '30', '35']
```

### Text Replacement

```python
import smrx

text = "The price is $5.99 and $10.50"
new_text, count = smrx.replace(
    text,
    r'\$(\d+\.\d{2})',
    r'USD \1',
    case_sensitive=True,
    count=0  # Replace all
)
# new_text: "The price is USD 5.99 and USD 10.50"
# count: 2
```

### Cache Management

```python
import smrx

# Get cache statistics
stats = smrx.get_stats()
print(stats)
# {'pattern_cache_size': 5, 'file_cache_size': 0, 'match_cache_size': 3}

# Clear all caches
smrx.clear_cache()
```

## Common Patterns

### Python Code

- Functions: `def\s+\w+\s*\(`
- Classes: `class\s+\w+`
- Imports: `^(?:from|import)\s+`
- Comments: `#\s*TODO|FIXME|XXX`
- Docstrings: `""".*?"""|'''.*?'''`

### Data Patterns

- Email: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- URLs: `https?://[^\s]+`
- Phone (US): `\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}`
- IP Address: `\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b`
- Hex Color: `#(?:[0-9a-fA-F]{3}){1,2}\b`

### Web Development

- HTML Tags: `<[a-zA-Z][^>]*>`
- CSS Classes: `\.[-_a-zA-Z0-9]+`
- JavaScript Variables: `(?:const|let|var)\s+(\w+)`
- JSON Keys: `"([^"]+)"\s*:`

## Performance Tips

1. **Use specific file patterns**: `--files '*.py'` instead of `*`
2. **Limit results**: `max_results` parameter to cap processing
3. **Case-insensitive searches** are slightly faster when not needed
4. **Binary file skipping** happens automatically
5. **Pattern caching** improves repeated searches on same pattern

## Limitations

- Binary files are automatically skipped
- Very large files (>100MB) may be slow to process
- Maximum result set is configurable (default: 1000)
- Pattern compilation errors are reported with error messages
- Encoding errors in files are handled gracefully (ignored)

## Example: Find All TODO Comments

```bash
# In chat mode
> find regex # TODO:.*

# Via CLI
python main.py regex-search '# TODO:.*' --files '*.py'

# Via Python
import smrx
result = smrx.search('.', r'# TODO:.*', file_pattern='*.py')
for match in result.matches:
    print(f"{match.filepath}:{match.line_num}: {match.match_text}")
```

## Example: Refactor Variable Names

```python
import smrx

# Find all instances of old_var
result = smrx.search('.', r'\bold_var\b', file_pattern='*.py')

# Then use replace for each file
for filepath in set(m.filepath for m in result.matches):
    content = open(filepath).read()
    new_content, count = smrx.replace(
        content,
        r'\bold_var\b',
        'new_var'
    )
    if count > 0:
        open(filepath, 'w').write(new_content)
        print(f"Updated {filepath}: {count} replacements")
```
